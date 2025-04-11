from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import random
import socket
import requests
import geocoder
from app import db  # Import the db object here
from models import Host, Proxies  # Ensure you're importing your models

# Create the blueprint
scans_bp = Blueprint('scans', __name__)

# Fetch the valid SOCKS5 proxies
def get_valid_proxies():
    return [p for p in Proxies.query.filter_by(status='active', type='SOCKS5')]

@scans_bp.route('/')
def run_scan_view():
    recent_scans = []  # You would typically load recent scans from your database
    hosts = Host.query.all()  # Get all hosts from the database
    return render_template('scans.html', recent_scans=recent_scans, hosts=hosts)

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    selected_hosts = request.form.getlist('hosts')  # Get selected host IDs
    scan_type = request.form.get('scan_type')  # The type of scan selected (e.g., "hostname", "port_check")

    valid_proxies = get_valid_proxies()

    if not valid_proxies:
        flash('No valid SOCKS5 proxies available!', 'error')
        return redirect(url_for('scans.run_scan_view'))

    for host_id in selected_hosts:
        host = Host.query.get(host_id)  # Get the host object from the DB
        if not host:
            continue

        # Perform the scan
        if scan_type == 'hostname':
            try:
                resolved_ip = socket.gethostbyname(host.name)
                host.resolved_hostname = resolved_ip
            except socket.gaierror:
                host.resolved_hostname = "Failed to resolve hostname"
        
        elif scan_type == 'port_check':
            open_ports = []
            for port in [80, 443]:
                try:
                    proxy = f"socks5://{valid_proxies[0].ip}:{valid_proxies[0].port}"
                    response = requests.get(f"http://{host.ip}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        open_ports.append(port)
                except requests.RequestException:
                    continue

            host.open_ports = str(open_ports)  # Store as a string
         
        # Get the location of the host IP (using geocoder)
        g = geocoder.ip(host.ip)
        host.location = f"{g.city}, {g.country}"  # Format location as city, country

        # Commit the changes to the database
        db.session.commit()

    flash('Scan completed and host data updated.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# View history of scans
@scans_bp.route('/history')
def scan_history():
    return render_template('scan_history.html', scans=[])  # You would populate this with actual scan history data
