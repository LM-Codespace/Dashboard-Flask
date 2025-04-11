# scans.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import socket
import requests
import geocoder  # To get location info based on IP

# Assuming you're using an ORM like SQLAlchemy
# Remove this line: from app import db
from models import Host, Scan  # Assuming you have a Scan model to track scan results

scans_bp = Blueprint('scans', __name__, url_prefix='/scans')

# Fetch the valid SOCKS5 proxies (adjust your proxy list source as needed)
def get_valid_proxies():
    return [p for p in proxies if p['status'] == 'active' and p['type'] == 'SOCKS5']

@scans_bp.route('/')
def run_scan_view():
    from app import db  # Import here to avoid circular import

    # Get recent scans and hosts to select from
    recent_scans = Scan.query.order_by(Scan.date.desc()).limit(5).all()  # Show last 5 scans
    hosts = Host.query.all()  # Get all hosts from the database
    return render_template('scans.html', recent_scans=recent_scans, hosts=hosts)

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    from app import db  # Import here to avoid circular import

    selected_hosts = request.form.getlist('hosts')  # Get selected host IDs
    scan_type = request.form.get('scan_type')  # The type of scan selected (e.g., "hostname", "port_check")

    valid_proxies = get_valid_proxies()

    if not valid_proxies:
        flash('No valid SOCKS5 proxies available!', 'error')
        return redirect(url_for('scans.run_scan_view'))

    # Create a new Scan record for tracking the scan
    scan = Scan(type=scan_type, status='in-progress', date=datetime.now())
    db.session.add(scan)
    db.session.commit()  # Commit to get the scan ID for tracking

    for host_id in selected_hosts:
        host = Host.query.get(host_id)  # Get the host object from the DB
        if not host:
            continue

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
                    proxy = f"socks5://{valid_proxies[0]['ip']}:{valid_proxies[0]['port']}"
                    response = requests.get(f"http://{host.ip}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        open_ports.append(port)
                except requests.RequestException as e:
                    continue

            host.open_ports = str(open_ports)  # Store as a comma-separated string, or JSON
         
        # Get the location of the host IP (using geocoder)
        g = geocoder.ip(host.ip)
        host.location = f"{g.city}, {g.country}"  # Format location as city, country

        # Link the scan to the host
        scan_result = {
            'host_id': host.id,
            'scan_id': scan.id,
            'open_ports': host.open_ports,
            'resolved_hostname': host.resolved_hostname,
            'location': host.location
        }

        # Commit the changes to the database
        db.session.commit()

    # Update scan status to 'completed' after processing
    scan.status = 'completed'
    db.session.commit()

    flash('Scan completed and host data updated.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# View history of scans (as before)
@scans_bp.route('/history')
def scan_history():
    from app import db  # Import here to avoid circular import
    scans = Scan.query.order_by(Scan.date.desc()).all()  # Get all scans, ordered by date
    return render_template('scan_history.html', scans=scans)

@scans_bp.route('/report/<int:scan_id>')
def view_report(scan_id):
    from app import db  # Import here to avoid circular import

    scan = Scan.query.get(scan_id)  # Get the scan object from the DB
    if not scan:
        flash(f'Scan ID {scan_id} not found.', 'error')
        return redirect(url_for('scans.scan_history'))

    # Get the results related to the scan
    scan_results = scan.hosts  # Assuming there's a relationship between scan and hosts

    return render_template('report.html', scan=scan, scan_results=scan_results)

@scans_bp.route('/reports')
def reports():
    from app import db  # Import here to avoid circular import
    # Here you can aggregate or filter reports as needed
    scans = Scan.query.order_by(Scan.date.desc()).all()  # Get all scans, ordered by date
    return render_template('reports.html', scans=scans)
