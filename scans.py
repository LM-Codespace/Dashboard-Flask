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
    return render_template('reports.html')

def perform_scan(scan_id, ip_address, proxy_id, scan_type):
    print(f"Performing scan for {scan_id} on {ip_address} with scan type {scan_type}.")
    nm = nmap.PortScanner()

    try:
        # Start scanning based on the scan type
        if scan_type == 'port_scan':
            print(f"Running port scan for {ip_address}.")
            nm.scan(ip_address, '1-65535')  # Scan all ports 1-65535

            # Example: Collect scan results and process them
            scan_results = nm[ip_address]  # Results for the scanned IP
            print(f"Scan results for {ip_address}: {scan_results}")

        # After completing the scan, update the status in the database
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Completed'  # Mark the scan as completed
            db.session.commit()

        print(f"Scan {scan_id} completed successfully.")

    except Exception as e:
        print(f"Scan failed for {ip_address}: {e}")
        # If the scan fails, mark it as failed in the database
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Failed'
            db.session.commit()

