from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Host, Proxies, Scan, db
from datetime import datetime
import socket
import socks
import threading
import random

scans_bp = Blueprint('scans', __name__)

# Helper to fetch active SOCKS5 proxies
def get_valid_proxies():
    # Use the correct model name "Proxies" (plural)
    proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()
    print(f"[Proxy Fetch] Retrieved {len(proxies)} active SOCKS5 proxies.")
    return proxies

@scans_bp.route('/', methods=['GET', 'POST'])
def run_scan_view():
    if request.method == 'POST':
        scan_type = request.form.get('scan_type')
        ip_address = request.form.get('ip_address')
        proxy_id = request.form.get('proxy_id') or None  # Ensure None if not provided
        scan_all = request.form.get('scan_all')  # Check if "Scan All Hosts" is selected

        if scan_all:
            ip_address = None
            proxy_id = None

        new_scan = Scan(
            date=datetime.now(),
            status='In Progress',
            scan_type=scan_type,
            ip_address=ip_address,
            proxy_id=proxy_id,
            results=None
        )

        try:
            with db.session.begin():
                db.session.add(new_scan)
                db.session.commit()
            return redirect(url_for('scans.reports'))
        except Exception as e:
            db.session.rollback()
            return f"An error occurred: {e}"

    hosts = Host.query.all()
    proxies = Proxies.query.all()  # Use Proxies instead of Proxy
    return render_template('scans.html', hosts=hosts, proxies=proxies)


@scans_bp.route('/run', methods=['POST'])
def run_scan():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    scan_type = request.form['scan_type']
    scan_all = request.form.get('scan_all') == 'true'

    if scan_all:
        print("[BULK SCAN] Starting scan of all hosts using all proxies.")
        
        # Fetch all hosts and proxies
        hosts = Host.query.with_entities(Host.ip_address).distinct().all()
        proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()  # Use Proxies instead of Proxy

        # Check if there are hosts or proxies available
        if not hosts or not proxies:
            flash("Missing hosts or proxies!", "danger")
            return redirect(url_for('scans.run_scan_view'))

        for idx, host in enumerate(hosts):
            # Ensure a proxy is assigned to each host, even when proxies are limited
            proxy = proxies[idx % len(proxies)]
            
            # Create a new scan for each host with the selected proxy
            new_scan = Scan(
                ip_address=host.ip_address,  # Ensure host IP is correctly assigned
                proxy_id=proxy.id,  # Ensure proxy is assigned correctly
                scan_type=scan_type,
                status='In Progress',
                date=datetime.utcnow()
            )
            db.session.add(new_scan)
            db.session.commit()

            print(f"[Bulk Scan] Created scan {new_scan.id} for IP {host.ip_address} using Proxy ID {proxy.id}")
            
            # Start the scan in a new thread
            t = threading.Thread(target=perform_scan, args=(new_scan.id, host.ip_address, proxy.id, scan_type))
            t.daemon = True  # Ensure the thread exits when the main program exits
            t.start()

        flash(f'Bulk scan initiated for {len(hosts)} hosts!', 'info')
        return redirect(url_for('scans.view_scans'))

    # Single scan scenario
    ip_address = request.form['ip_address']
    proxy_id = request.form.get('proxy_id')  # Get the proxy ID, may be None if not selected

    # Ensure a valid proxy ID is selected for single scans
    if not proxy_id:
        flash("Please select a proxy for the scan.", "danger")
        return redirect(url_for('scans.run_scan_view'))

    # Create a new scan record
    new_scan = Scan(
        ip_address=ip_address,
        proxy_id=proxy_id,
        scan_type=scan_type,
        status='In Progress',
        date=datetime.utcnow()
    )
    db.session.add(new_scan)
    db.session.commit()
    scan_id = new_scan.id

    print(f"[Single Scan] Starting scan {scan_id} for IP: {ip_address} using Proxy ID {proxy_id}")
    
    # Start the scan in a new thread
    t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy_id, scan_type))
    t.daemon = True  # Ensure the thread exits when the main program exits
    t.start()

    flash('Scan started successfully!', 'success')
    return redirect(url_for('scans.view_scans'))


@scans_bp.route('/history')
def scan_history():
    scans = Scan.query.order_by(Scan.date.desc()).all()
    return render_template('scan_history.html', scans=scans)


@scans_bp.route('/reports')
def reports():
    scans = Scan.query.order_by(Scan.date.desc()).all()
    return render_template('reports.html', scans=scans)


def perform_scan(scan_id, ip_address, proxy_id, scan_type):
    print(f"\n[Scan Start] ID: {scan_id} | Target: {ip_address} | Type: {scan_type}")

    try:
        proxies = get_valid_proxies()
        if not proxies:
            raise Exception("No active SOCKS5 proxies found in DB.")

        proxy = random.choice(proxies)
        print(f"[Proxy Selected] {proxy.ip_address}:{proxy.port}")

        socks.set_default_proxy(socks.SOCKS5, proxy.ip_address, proxy.port)
        socket.socket = socks.socksocket

        results_str = ""

        if scan_type == 'port_scan':
            open_ports = []
            for port in range(1, 1025):
                try:
                    s = socket.socket()
                    s.settimeout(1.5)
                    s.connect((ip_address, port))
                    open_ports.append(str(port))
                    s.close()
                except:
                    continue
            results_str = "Open Ports: " + ", ".join(open_ports) if open_ports else "No open ports found"

        elif scan_type == 'hostname_scan':
            try:
                resolved_hostname = socket.gethostbyaddr(ip_address)
                results_str = f"Resolved Hostname: {resolved_hostname[0]}"
            except socket.herror as e:
                results_str = f"Hostname resolution failed: {e}"

        elif scan_type == 'os_detection':
            results_str = "OS detection is not supported over SOCKS5 proxies."

        else:
            results_str = "Unknown scan type."

        # Log the results before updating the database
        print(f"[Scan Results] Scan ID: {scan_id} | Results: {results_str}")

        # Update the scan status and results
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Completed'
            scan.results = results_str
            db.session.commit()

        print(f"[Scan Completed] ID: {scan_id} | Status: Completed\n")

    except Exception as e:
        error_message = f"Scan failed due to: {str(e)}"
        print(f"[Error] {error_message}")
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Failed'
            scan.results = error_message
            db.session.commit()
