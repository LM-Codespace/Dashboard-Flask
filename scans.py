from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Host, Proxies, Scan, db
from datetime import datetime
import socket
import socks
import threading
import random
import struct
import logging
from contextlib import contextmanager

# Configure logger
logger = logging.getLogger(__name__)

scans_bp = Blueprint('scans', __name__)

# Function to perform port scan
def perform_port_scan(ip_address, proxy_id):
    """Perform a port scan on a given IP address"""
    open_ports = []
    for port in [21, 22, 80, 443, 3389]:  # Common ports for testing
        try:
            s = socks.socksocket()
            s.settimeout(3)  # Increased timeout for proxy connections
            s.connect((ip_address, port))
            open_ports.append(str(port))
            s.close()
        except Exception as e:
            logger.error(f"Port {port} closed or error: {str(e)}")
            continue
    return "Open Ports: " + ", ".join(open_ports) if open_ports else "No open ports found"

# Function to perform hostname scan
def perform_hostname_scan(ip_address, proxy_id):
    """Perform a hostname resolution scan on a given IP address"""
    try:
        socks.set_default_proxy(socks.SOCKS5, proxy.ip_address, proxy.port, rdns=True)
        socket.socket = socks.socksocket
        resolved_hostname = socket.gethostbyaddr(ip_address)
        return f"Resolved Hostname: {resolved_hostname[0]}"
    except socket.herror as e:
        return f"Hostname resolution failed: {e}"
    except Exception as e:
        return f"Error during hostname resolution: {e}"

# Scan Handlers Dictionary to map scan types to functions
scan_handlers = {
    'port_scan': perform_port_scan,
    'hostname_scan': perform_hostname_scan,
}

# Helper function to get proxy by ID
def get_proxy_by_id(proxy_id):
    return Proxies.query.filter_by(id=proxy_id, status='active', type='SOCKS5').first()

# Context manager to use a SOCKS5 proxy
@contextmanager
def use_proxy(proxy):
    """Context manager for using a proxy."""
    try:
        setup_socks5_proxy(proxy)
        yield
    finally:
        # Reset proxy settings after use
        socks.set_default_proxy()
        socket.socket = socket._socketobject

# Function to setup SOCKS5 proxy
def setup_socks5_proxy(proxy):
    """Helper function to properly configure SOCKS5 proxy"""
    try:
        # Reset any previous proxy settings
        socks.set_default_proxy()
        socket.socket = socket._socketobject  # Reset to default socket
        
        # Set up the new proxy
        socks.set_default_proxy(
            socks.SOCKS5,
            proxy.ip_address,
            proxy.port,
            rdns=True,  # Enable remote DNS resolution
            username=proxy.username if hasattr(proxy, 'username') else None,
            password=proxy.password if hasattr(proxy, 'password') else None
        )
        socket.socket = socks.socksocket
        return True
    except Exception as e:
        logger.error(f"[Proxy Setup Error] Failed to setup proxy {proxy.ip_address}:{proxy.port}: {str(e)}")
        return False

# Function to test proxy connection
def test_proxy_connection(proxy, test_ip="8.8.8.8", test_port=53, timeout=5):
    """Test if the proxy is working by connecting to a known IP"""
    try:
        with use_proxy(proxy):
            s = socks.socksocket()
            s.settimeout(timeout)
            s.connect((test_ip, test_port))
            s.close()
        return True
    except Exception as e:
        logger.error(f"[Proxy Test Failed] Proxy {proxy.ip_address}:{proxy.port} failed: {str(e)}")
        return False

# Function to handle individual scans
def perform_scan(scan_id, ip_address, proxy_id, scan_type):
    """Perform a scan and update the results"""
    try:
        logger.info(f"Starting scan for Scan ID: {scan_id}, IP: {ip_address}, Proxy ID: {proxy_id}, Type: {scan_type}")
        
        if scan_type not in scan_handlers:
            raise Exception(f"Unknown scan type: {scan_type}")
        
        # Get the handler function and execute it
        handler = scan_handlers[scan_type]
        results_str = handler(ip_address, proxy_id)
        
        logger.info(f"Scan completed for Scan ID: {scan_id}, Results: {results_str}")
        
        # Update the scan results in the database
        update_scan_results(scan_id, 'Completed', results_str)
    except Exception as e:
        logger.error(f"Scan failed for ID {scan_id} | Error: {str(e)}")
        update_scan_results(scan_id, 'Failed', str(e))

# Function to update scan results
def update_scan_results(scan_id, status, results_str):
    """Update scan status and results in the database"""
    with db.session.begin():
        scan = Scan.query.get(scan_id)
        scan.status = status
        scan.results = results_str
        db.session.commit()
    logger.info(f"[Scan Results] Scan ID: {scan_id} | Status: {status} | Results: {results_str}")

# Route for running a scan
@scans_bp.route('/', methods=['GET', 'POST'])
def run_scan_view():
    if request.method == 'POST':
        scan_type = request.form.get('scan_type')
        ip_address = request.form.get('ip_address')
        proxy_id = request.form.get('proxy_id') or None
        scan_all = request.form.get('scan_all')

        if scan_all:
            ip_address = None
            proxy_id = None

        new_scan = Scan(
            date=datetime.now(),
            status='In Progress',
            scan_type=scan_type,
            ip_address=ip_address,
            proxy_id=proxy_id,
            results=None
        )

        try:
            db.session.add(new_scan)
            db.session.commit()
            return redirect(url_for('scans.reports'))  # Updated to 'scans.reports'
        except Exception as e:
            db.session.rollback()
            return f"An error occurred: {str(e)}"

    hosts = Host.query.all()
    proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()
    return render_template('scans.html', hosts=hosts, proxies=proxies)

# New route for reports page (this was missing)
@scans_bp.route('/reports', methods=['GET'])
def reports():
    """View the scan reports"""
    scans = Scan.query.all()  # You can refine this query based on your needs
    return render_template('reports.html', scans=scans)

# Route to handle running a scan (single scan or bulk scan)
@scans_bp.route('/run', methods=['POST'])
def run_scan():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    scan_type = request.form['scan_type']
    scan_all = request.form.get('scan_all') == 'true'

    if scan_all:
        logger.info("[BULK SCAN] Starting scan of all hosts using all proxies.")
        hosts = Host.query.with_entities(Host.ip_address).distinct().all()
        proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()

        if not hosts or not proxies:
            flash("Missing hosts or proxies!", "danger")
            return redirect(url_for('scans.run_scan_view'))

        for idx, host in enumerate(hosts):
            proxy = proxies[idx % len(proxies)]
            
            # Test proxy before using it
            if not test_proxy_connection(proxy):
                logger.warning(f"[Bulk Scan] Skipping bad proxy {proxy.ip_address}:{proxy.port}")
                continue
                
            new_scan = Scan(
                ip_address=host.ip_address,
                proxy_id=proxy.id,
                scan_type=scan_type,
                status='In Progress',
                date=datetime.utcnow()
            )
            db.session.add(new_scan)
            db.session.commit()

            logger.info(f"[Bulk Scan] Created scan {new_scan.id} for IP {host.ip_address} using Proxy ID {proxy.id}")
            
            t = threading.Thread(target=perform_scan, args=(new_scan.id, host.ip_address, proxy.id, scan_type))
            t.daemon = True
            t.start()

        flash(f'Bulk scan initiated for {len(hosts)} hosts!', 'info')
        return redirect(url_for('scans.view_scans'))

    # Single scan scenario
    ip_address = request.form['ip_address']
    proxy_id = request.form.get('proxy_id')

    if not proxy_id:
        flash("Please select a proxy for the scan.", "danger")
        return redirect(url_for('scans.run_scan_view'))

    proxy = get_proxy_by_id(proxy_id)
    if not proxy:
        flash("Selected proxy is not available.", "danger")
        return redirect(url_for('scans.run_scan_view'))

    # Test proxy before using it
    if not test_proxy_connection(proxy):
        flash("Selected proxy is not working. Please try another one.", "danger")
        return redirect(url_for('scans.run_scan_view'))

    new_scan = Scan(
        ip_address=ip_address,
        proxy_id=proxy_id,
        scan_type=scan_type,
        status='In Progress',
        date=datetime.utcnow()
    )
    db.session.add(new_scan)
    db.session.commit()
    scan_id = new_scan.id

    logger.info(f"[Single Scan] Starting scan {scan_id} for IP: {ip_address} using Proxy ID {proxy_id}")
    
    t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy_id, scan_type))
    t.daemon = True
    t.start()

    flash('Scan started successfully!', 'success')
    return redirect(url_for('scans.view_scans'))
