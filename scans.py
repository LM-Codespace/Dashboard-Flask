from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Host, Proxies, Scan, db  # Import db from models
import socket
import requests
import geocoder  # Assuming geocoder is used for IP geolocation

scans_bp = Blueprint('scans', __name__)

def get_valid_proxies():
    # Returns a list of active SOCKS5 proxies from the database
    return [p for p in Proxies.query.filter_by(status='active', type='SOCKS5')]

@scans_bp.route('/')
def run_scan_view():
    # Retrieve recent scans or other data to display
    recent_scans = Scan.query.order_by(Scan.date.desc()).limit(5).all()  # Example: load recent scans
    hosts = Host.query.all()  # Get all hosts from the database
    return render_template('scans.html', recent_scans=recent_scans, hosts=hosts)

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    selected_hosts = request.form.getlist('hosts')  # Get selected host IDs from the form
    scan_type = request.form.get('scan_type')  # The type of scan selected (e.g., "hostname", "port_check")

    # Get available SOCKS5 proxies
    valid_proxies = get_valid_proxies()

    if not valid_proxies:
        flash('No valid SOCKS5 proxies available!', 'error')
        return redirect(url_for('scans.run_scan_view'))

    # Loop over selected hosts
    for host_id in selected_hosts:
        host = Host.query.get(host_id)  # Get the host object from the database
        if not host:
            continue

        # Create a Scan record to track this scan
        new_scan = Scan(date=datetime.utcnow(), status='In Progress', type=scan_type, host=host)
        db.session.add(new_scan)

        # Perform the scan based on the scan type
        if scan_type == 'hostname':
            try:
                resolved_ip = socket.gethostbyname(host.name)  # Resolve hostname to IP
                host.resolved_hostname = resolved_ip
            except socket.gaierror:
                host.resolved_hostname = "Failed to resolve hostname"
        
        elif scan_type == 'port_check':
            open_ports = []
            for port in [80, 443]:  # Check common HTTP(S) ports
                try:
                    proxy = f"socks5://{valid_proxies[0].ip_address}:{valid_proxies[0].port}"
                    response = requests.get(f"http://{host.ip}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                    if response.status_code == 200:
                        open_ports.append(port)
                except requests.RequestException:
                    continue

            host.open_ports = str(open_ports)  # Store open ports as a string
        
        # Get the location of the host IP (using geocoder)
        g = geocoder.ip(host.ip)
        host.location = f"{g.city}, {g.country}"  # Format location as city, country

        # Commit changes to the host
        db.session.commit()

        # Update scan status to 'Completed' after the scan is finished
        new_scan.status = 'Completed'
        db.session.commit()

    flash('Scan completed and host data updated.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# View history of scans
@scans_bp.route('/history')
def scan_history():
    # Fetch a list of all completed scans from the database
    scans = Scan.query.order_by(Scan.date.desc()).all()  # List all scans, order by date
    return render_template('scan_history.html', scans=scans)

# Placeholder for reports (implement as needed)
@scans_bp.route('/reports')
def reports():
    return render_template('reports.html')
