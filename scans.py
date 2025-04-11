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
    # Implement your database connection logic here
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

        # Get the proxy details
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if proxy_id:
                    cursor.execute('SELECT * FROM proxies WHERE id=%s', (proxy_id,))
                    proxy = cursor.fetchone()
                else:
                    proxy = None
                
                cursor.execute('INSERT INTO scan (ip_address, scan_type, status) VALUES (%s, %s, %s)', 
                             (ip_address, scan_type, 'In Progress'))
                connection.commit()
                scan_id = cursor.lastrowid
        finally:
            connection.close()

        t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy, scan_type))
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

def perform_scan(scan_id, ip_address, proxy, scan_type):
    nm = nmap.PortScanner()
    if scan_type == 'port_scan':
        try:
            if proxy:
                # Implement proxy handling here
                pass
                
            nm.scan(ip_address, '1-65535')
            
            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE scan SET status=%s WHERE id=%s', ('Completed', scan_id))
                    connection.commit()
            finally:
                connection.close()

        except Exception as e:
            print(f"Scan failed: {e}")
