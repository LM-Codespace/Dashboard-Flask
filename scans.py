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
    proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()
    print(f"[Proxy Fetch] Retrieved {len(proxies)} active SOCKS5 proxies.")
    return proxies


@scans_bp.route('/', methods=['GET', 'POST'])
def run_scan_view():
    if request.method == 'POST':
        ip_address = request.form.get('ip_address')
        proxy_id = request.form.get('proxy_id')  # Optional; can be None
        scan_type = request.form.get('scan_type')

        new_scan = Scan(
            ip_address=ip_address,
            proxy_id=proxy_id,
            scan_type=scan_type,
            status='In Progress',
            date=datetime.utcnow()
        )
        db.session.add(new_scan)
        db.session.commit()

        flash('Scan initiated successfully!', 'success')
        print(f"[Scan Created] ID: {new_scan.id} | IP: {ip_address} | Type: {scan_type} | Proxy ID: {proxy_id}")
        return redirect(url_for('scans.run_scan_view'))

    hosts = Host.query.with_entities(Host.ip_address).distinct().all()
    proxies = Proxies.query.all()

    print(f"[UI Load] Hosts retrieved: {len(hosts)} | First Host: {hosts[0].ip_address if hosts else 'None'}")
    return render_template('scans.html', hosts=hosts, proxies=proxies)


@scans_bp.route('/run', methods=['POST'])
def run_scan():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    scan_type = request.form['scan_type']
    ip_address = request.form['ip_address']
    proxy_id = request.form.get('proxy_id')

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
    print(f"[Threading] Starting thread for Scan ID: {scan_id} | IP: {ip_address} | Type: {scan_type}")

    t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy_id, scan_type))
    t.daemon = True
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
        # Step 1: Get a proxy
        proxies = get_valid_proxies()
        if not proxies:
            raise Exception("No active SOCKS5 proxies found in DB.")

        proxy = random.choice(proxies)
        print(f"[Proxy Selected] {proxy.ip_address}:{proxy.port}")

        # Step 2: Set global SOCKS5 proxy
        socks.set_default_proxy(socks.SOCKS5, proxy.ip_address, proxy.port)
        socket.socket = socks.socksocket

        results_str = ""

        # Step 3: Perform the selected scan type
        if scan_type == 'port_scan':
            print(f"[Scan] Starting manual port scan on {ip_address} (ports 1-1024)")
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
            print(f"[Result] {results_str}")

        elif scan_type == 'hostname_scan':
            print(f"[Scan] Attempting reverse DNS lookup for {ip_address}")
            try:
                resolved_hostname = socket.gethostbyaddr(ip_address)
                results_str = f"Resolved Hostname: {resolved_hostname[0]}"
            except socket.herror as e:
                results_str = f"Hostname resolution failed: {e}"
            print(f"[Result] {results_str}")

        elif scan_type == 'os_detection':
            results_str = "OS detection is not supported over SOCKS5 proxies."
            print(f"[Result] {results_str}")

        else:
            results_str = "Unknown scan type."
            print(f"[Error] {results_str}")

        # Step 4: Save results
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
