from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import random
import socket
import requests
import geocoder

# Import db here to avoid circular import
from app import db

# Import models (ensure they are defined in models.py)
from models import Proxies, Host

scans_bp = Blueprint('scans', __name__)

# Function to get active SOCKS5 proxies from the database
def get_valid_proxies():
    return [p for p in Proxies.query.filter_by(status='active', type='SOCKS5')]

# View for running scans
@scans_bp.route('/')
def run_scan_view():
    recent_scans = []  # You would typically load recent scans from your database
    hosts = Host.query.all()  # Get all hosts from the database
    return render_template('scans.html', recent_scans=recent_scans, hosts=hosts)

# Route to run the scan
@scans_bp.route('/run', methods=['POST'])
def run_scan():
    selected_hosts = request.form.getlist('hosts')  # Get selected host IDs
    scan_type = request.form.get('scan_type')  # The type of scan selected (e.g., "hostname", "port_check")

    # Fetch valid proxies for the scan
    valid_proxies = get_valid_proxies()

    if not valid_proxies:
        flash('No valid SOCKS5 proxies available!', 'error')
        return redirect(url_for('scans.run_scan_view'))

    # Iterate over the selected hosts and run the appropriate scan
    for host_id in selected_hosts:
        host = Host.query.get(host_id)  # Get the host object from the DB
        if not host:
            continue

        # Perform the scan based on the selected scan type
        if scan_type == 'hostname':
            try:
                resolved_ip = socket.gethostbyname(host.name)  # Resolve hostname to IP
                host.resolved_hostname = resolved_ip
            except socket.gaierror:
                host.resolved_hostname = "Failed to resolve hostname"
        
        elif scan_type == 'port_check':
            open_ports = []
            for port in [80, 443]:  # Check common ports (HTTP, HTTPS)
                try:
                    # Use the first available proxy for port checking
                    proxy = f"socks5://{valid_proxies[0].ip}:{valid_proxies[0].port}"
                    response = requests.get(f"http://{host.ip}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        open_ports.append(port)
                except requests.RequestException:
                    continue

            # Store open ports as a string in the host model
            host.open_ports = str(open_ports)  

        # Get the location of the host IP using geocoder (city, country)
        g = geocoder.ip(host.ip)
        host.location = f"{g.city}, {g.country}"  # Format location as city, country

        # Commit changes to the database
        db.session.commit()

    flash('Scan completed and host data updated.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# View history of scans (to be implemented)
@scans_bp.route('/history')
def scan_history():
    scans = []  # Populate this with actual scan history data
    return render_template('scan_history.html', scans=scans)  # Scan history will be displayed here
