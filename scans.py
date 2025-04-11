from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Host, Proxies, Scan, db
from datetime import datetime
import socket
import requests
import geocoder
import threading
import nmap

scans_bp = Blueprint('scans', __name__)

def get_db_connection():
    # Implement your database connection logic here if needed
    pass

def get_valid_proxies():
    # Returns a list of active SOCKS5 proxies from the database
    return [p for p in Proxies.query.filter_by(status='active', type='SOCKS5')]

@scans_bp.route('/', methods=['GET', 'POST'])
def run_scan_view():
    if request.method == 'POST':
        # Handle scan initiation here
        ip_address = request.form.get('ip_address')
        proxy_id = request.form.get('proxy_id')
        scan_type = request.form.get('scan_type')

        # Example: Start the scan logic here
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
        print(f"New scan created for IP: {ip_address}, Scan type: {scan_type}, Proxy ID: {proxy_id}")
        return redirect(url_for('scans.run_scan_view'))

    # Fetch available IPs from the hosts table (which we know has data)
    hosts = Host.query.with_entities(Host.ip_address).distinct().all()  # Get only IP addresses
    proxies = Proxies.query.all()  # Query the proxies table

    # Debug output
    print(f"Hosts retrieved: {len(hosts)}")
    if hosts:
        print(f"First host IP: {hosts[0].ip_address}")

    return render_template('scans.html', hosts=hosts, proxies=proxies)

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    if 'loggedin' in session:
        # Get form data
        scan_type = request.form['scan_type']
        ip_address = request.form['ip_address']
        proxy_id = request.form.get('proxy_id')

        # Create a new scan entry in the database
        new_scan = Scan(
            ip_address=ip_address,
            proxy_id=proxy_id,
            scan_type=scan_type,
            status='In Progress',
            date=datetime.utcnow()
        )
        db.session.add(new_scan)
        db.session.commit()
        scan_id = new_scan.id  # Get the newly created scan's ID

        # Debug print to confirm the scan data
        print(f"Starting scan {scan_id} for IP: {ip_address} with scan type {scan_type}.")

        # Start the scan in a separate thread to avoid blocking
        print(f"Creating thread for scan {scan_id}.")
        t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy_id, scan_type))
        t.daemon = True  # Ensures the thread will close when the main process exits
        t.start()

        flash('Scan started successfully!', 'success')
        return redirect(url_for('scans.view_scans'))
    return redirect(url_for('auth.login'))

@scans_bp.route('/history')
def scan_history():
    scans = Scan.query.order_by(Scan.date.desc()).all()
    return render_template('scan_history.html', scans=scans)

@scans_bp.route('/reports')
def reports():
    # Query all the scan records from the database
    scans = Scan.query.order_by(Scan.date.desc()).all()  # Order scans by date (newest first)
    return render_template('reports.html', scans=scans)


import socks
import socket
import random
from models import db, Scan, Proxies

def perform_scan(scan_id, ip_address, proxy_id, scan_type):
    print(f"Starting scan ID {scan_id} | Type: {scan_type} | IP: {ip_address}")

    try:
        # Get all active proxies
        proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()
        if not proxies:
            raise Exception("No active SOCKS5 proxies available")

        # Choose a proxy (randomly for this scan session)
        proxy = random.choice(proxies)
        print(f"Using proxy: {proxy.ip_address}:{proxy.port}")

        # Set global proxy for sockets
        socks.set_default_proxy(socks.SOCKS5, proxy.ip_address, proxy.port)
        socket.socket = socks.socksocket  # Patch socket

        results_str = ""

        if scan_type == 'port_scan':
            print("Performing SOCKS5 port scan manually...")
            open_ports = []
            for port in range(1, 1025):  # You can increase the range if needed
                try:
                    s = socket.socket()
                    s.settimeout(2)
                    s.connect((ip_address, port))
                    open_ports.append(str(port))
                    s.close()
                except Exception:
                    continue
            results_str = "Open Ports: " + ", ".join(open_ports) if open_ports else "No open ports found"

        elif scan_type == 'hostname_scan':
            print("Performing hostname resolution over proxy...")
            try:
                resolved_hostname = socket.gethostbyaddr(ip_address)
                results_str = f"Resolved Hostname: {resolved_hostname[0]}"
            except socket.herror as e:
                results_str = "Hostname resolution failed"

        elif scan_type == 'os_detection':
            results_str = "OS detection is not supported over SOCKS5 proxies via nmap."

        # Update DB with results
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Completed'
            scan.results = results_str
            db.session.commit()

        print(f"Scan {scan_id} completed: {results_str}")

    except Exception as e:
        print(f"Scan {scan_id} failed: {e}")
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Failed'
            scan.results = f"Scan failed: {str(e)}"
            db.session.commit()

