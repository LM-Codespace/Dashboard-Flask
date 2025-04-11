from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import random
import socket
import requests

# Simulated storage for scans — replace with DB later
scan_results = []

# Simulated storage for hosts and proxies — replace with DB calls
hosts = [
    {'id': 1, 'name': 'example.com', 'ip': '93.184.216.34'},
    {'id': 2, 'name': 'localhost', 'ip': '127.0.0.1'}
]

proxies = [
    {'id': 1, 'ip': '127.0.0.1', 'port': 1080, 'type': 'SOCKS5', 'status': 'active'},
    {'id': 2, 'ip': '192.168.1.1', 'port': 1080, 'type': 'SOCKS5', 'status': 'inactive'}
]

# Fetch the valid SOCKS5 proxies
def get_valid_proxies():
    return [p for p in proxies if p['status'] == 'active' and p['type'] == 'SOCKS5']

# Main scan page showing recent scans and available hosts
@scans_bp.route('/')
def run_scan_view():
    recent_scans = scan_results[-5:]  # Show last 5 scans
    return render_template('scans.html', recent_scans=recent_scans, hosts=hosts)

# Trigger a scan with selected hosts and proxy
@scans_bp.route('/run', methods=['POST'])
def run_scan():
    selected_hosts = request.form.getlist('hosts')  # Get the list of selected host IDs
    scan_type = request.form.get('scan_type')  # The type of scan selected (e.g., "hostname", "port_check")

    # Get the valid proxies
    valid_proxies = get_valid_proxies()

    if not valid_proxies:
        flash('No valid SOCKS5 proxies available!', 'error')
        return redirect(url_for('scans.run_scan_view'))

    scan_results_for_this_run = []

    # Perform the scans
    for host in selected_hosts:
        host_data = next((h for h in hosts if str(h['id']) == host), None)
        if host_data:
            scan_result = {}
            scan_result['host'] = host_data
            scan_result['scan_type'] = scan_type
            scan_result['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            scan_result['result'] = None

            if scan_type == 'hostname':
                # Try resolving the hostname
                try:
                    resolved_ip = socket.gethostbyname(host_data['name'])
                    scan_result['result'] = f"Hostname resolved to {resolved_ip}"
                except socket.gaierror:
                    scan_result['result'] = "Failed to resolve hostname"
            
            elif scan_type == 'port_check':
                # Example port check: check if 80 or 443 is open
                for port in [80, 443]:
                    try:
                        # Use requests with proxy to check if the server is reachable
                        proxy = f"socks5://{valid_proxies[0]['ip']}:{valid_proxies[0]['port']}"
                        response = requests.get(f"http://{host_data['ip']}:{port}", proxies={"http": proxy, "https": proxy}, timeout=5)
                        if response.status_code == 200:
                            scan_result['result'] = f"Port {port} is open"
                        else:
                            scan_result['result'] = f"Port {port} is closed"
                    except requests.RequestException as e:
                        scan_result['result'] = f"Error checking port {port}: {str(e)}"
            
            scan_results_for_this_run.append(scan_result)

    # Add the results of the current scan to the global scan_results
    scan_results.extend(scan_results_for_this_run)

    flash('Scan completed successfully.', 'success')
    return redirect(url_for('scans.run_scan_view'))

# Show full scan history
@scans_bp.route('/history')
def scan_history():
    return render_template('scan_history.html', scans=scan_results)

# View report for specific scan
@scans_bp.route('/report/<int:scan_id>')
def view_report(scan_id):
    scan = next((s for s in scan_results if s['id'] == scan_id), None)
    if not scan:
        flash(f'Scan ID {scan_id} not found.', 'error')
        return redirect(url_for('scans.scan_history'))
    return render_template('report.html', scan=scan)

# General reports page
@scans_bp.route('/reports')
def reports():
    return render_template('reports.html', scans=scan_results)
