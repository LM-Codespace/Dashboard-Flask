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
    if 'loggedin' in session:
        # Get form data
        scan_type = request.form['scan_type']
        ip_address = request.form['ip_address']
        proxy_id = request.form.get('proxy_id')  # Optional, in case you want to use proxies

        # Get the proxy details
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                # If the proxy is selected, fetch the proxy details
                if proxy_id:
                    cursor.execute('SELECT * FROM proxies WHERE id=%s', (proxy_id,))
                    proxy = cursor.fetchone()
                else:
                    proxy = None
                
                # Add a new scan entry in the DB with ip_address directly
                cursor.execute('INSERT INTO scan (ip_address, scan_type, status) VALUES (%s, %s, %s)', 
                               (ip_address, scan_type, 'In Progress'))
                connection.commit()
                scan_id = cursor.lastrowid
        finally:
            connection.close()

        # Perform the scan (could be a separate function or thread)
        t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy, scan_type))
        t.start()

        flash('Scan started successfully!', 'success')
        return redirect(url_for('scans.view_scans'))
    return redirect(url_for('auth.login'))

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

import nmap  # For port scanning, or use other libraries depending on the scan type
import time

def perform_scan(scan_id, ip_address, proxy, scan_type):
    # Example: Perform scan based on scan_type
    # Here, we use nmap for port scanning. You can expand this function for other types of scans.
    nm = nmap.PortScanner()

    if scan_type == 'port_scan':
        # Scan the host for open ports
        try:
            # Example using the nmap scanner
            if proxy:
                # Example: Use proxy if needed
                pass  # Implement proxy handling here
                
            nm.scan(ip_address, '1-65535')  # Scan all ports
            
            # Store results in the scan table (after the scan is complete)
            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE scan SET status=%s WHERE id=%s', ('Completed', scan_id))
                    connection.commit()
            finally:
                connection.close()

            # Optionally, you can also store detailed scan results in a results table or log
        except Exception as e:
            print(f"Scan failed: {e}")
            pass

