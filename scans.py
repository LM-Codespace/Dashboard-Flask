from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import socket
import requests
import geocoder  # To get location info based on IP
from models import Host, Scan, Proxies, db  # Import Proxies here

scans_bp = Blueprint('scans', __name__)

# Fetch the valid SOCKS5 proxies from the database
def get_valid_proxies():
    return [p for p in Proxies.query.filter_by(status='active', type='SOCKS5')]

@scans_bp.route('/')
def run_scan_view():
    recent_scans = Scan.query.order_by(Scan.date.desc()).limit(5).all()  # Show last 5 scans from the DB
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

        # Create a new Scan record to track the scan
        scan = Scan(
            type=scan_type,
            status='in-progress',
            date=datetime.utcnow(),
            host=host
        )
        db.session.add(scan)
        db.session.commit()

        # Perform the scan
        if scan_type == 'hostname':
            # Try resolving the hostname
            try:
                resolved_ip = socket.gethostbyname(host.name)
                host.resolved_hostname = resolved_ip
            except socket.gaierror:
                host.resolved_hostname = "Failed to resolve hostname"
        
        elif scan_type == 'port_check':
            open_ports = []

            # Check for open ports (80, 443) using the proxy
            for port in [80, 443]:
                try:
                    proxy = f"socks5://{valid_proxies[0].ip}:{valid_proxies[0].port}"
                    response = requests.get(f"http://{host.ip}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        open_ports.append(port)
                except requests.RequestException as e:
                    continue

            host.open_ports = str(open_ports)  # Store as a comma-separated string, or JSON
         
        # Get the location of the host IP (using geocoder)
        g = geocoder.ip(host.ip)
        host.location = f"{g.city}, {g.country}"  # Format location as city, country

        # Update the scan status to 'completed' and associate with the host
        scan.status = 'completed'
        db.session.commit()

        # Commit the changes to the database
        db.session.commit()

    flash('Scan completed and host data updated.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# View history of scans (fetch from DB)
@scans_bp.route('/history')
def scan_history():
    scans = Scan.query.order_by(Scan.date.desc()).all()  # Get all scan history from DB
    return render_template('scan_history.html', scans=scans)

# View detailed report of a scan
@scans_bp.route('/report/<int:scan_id>')
def view_report(scan_id):
    scan = Scan.query.get(scan_id)  # Fetch the scan from the DB
    if not scan:
        flash(f'Scan ID {scan_id} not found.', 'error')
        return redirect(url_for('scans.scan_history'))
    return render_template('report.html', scan=scan)

# View all reports (fetch scan results from DB)
@scans_bp.route('/reports')
def reports():
    scans = Scan.query.all()  # Fetch all scans
    return render_template('reports.html', scans=scans)
