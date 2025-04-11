from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Host, Proxies, Scan, db
from datetime import datetime
import socket
import socks
import threading
import random
import struct

scans_bp = Blueprint('scans', __name__)

def get_proxy_by_id(proxy_id):
    return Proxies.query.filter_by(id=proxy_id, status='active', type='SOCKS5').first()

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
        print(f"[Proxy Setup Error] Failed to setup proxy {proxy.ip_address}:{proxy.port}: {str(e)}")
        return False

def test_proxy_connection(proxy, test_ip="8.8.8.8", test_port=53, timeout=5):
    """Test if the proxy is working by connecting to a known IP"""
    try:
        if not setup_socks5_proxy(proxy):
            return False
            
        s = socks.socksocket()
        s.settimeout(timeout)
        s.connect((test_ip, test_port))
        s.close()
        return True
    except Exception as e:
        print(f"[Proxy Test Failed] Proxy {proxy.ip_address}:{proxy.port} failed: {str(e)}")
        return False
    finally:
        # Reset proxy settings after test
        socks.set_default_proxy()
        socket.socket = socket._socketobject

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
            return redirect(url_for('scans.reports'))
        except Exception as e:
            db.session.rollback()
            return f"An error occurred: {str(e)}"

    hosts = Host.query.all()
    proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()
    return render_template('scans.html', hosts=hosts, proxies=proxies)

@scans_bp.route('/run', methods=['POST'])
def run_scan():
    if 'loggedin' not in session:
        return redirect(url_for('auth.login'))

    scan_type = request.form['scan_type']
    scan_all = request.form.get('scan_all') == 'true'

    if scan_all:
        print("[BULK SCAN] Starting scan of all hosts using all proxies.")
        hosts = Host.query.with_entities(Host.ip_address).distinct().all()
        proxies = Proxies.query.filter_by(status='active', type='SOCKS5').all()

        if not hosts or not proxies:
            flash("Missing hosts or proxies!", "danger")
            return redirect(url_for('scans.run_scan_view'))

        for idx, host in enumerate(hosts):
            proxy = proxies[idx % len(proxies)]
            
            # Test proxy before using it
            if not test_proxy_connection(proxy):
                print(f"[Bulk Scan] Skipping bad proxy {proxy.ip_address}:{proxy.port}")
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

            print(f"[Bulk Scan] Created scan {new_scan.id} for IP {host.ip_address} using Proxy ID {proxy.id}")
            
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

    print(f"[Single Scan] Starting scan {scan_id} for IP: {ip_address} using Proxy ID {proxy_id}")
    
    t = threading.Thread(target=perform_scan, args=(scan_id, ip_address, proxy_id, scan_type))
    t.daemon = True
    t.start()

    flash('Scan started successfully!', 'success')
    return redirect(url_for('scans.view_scans'))

def perform_scan(scan_id, ip_address, proxy_id, scan_type):
    print(f"\n[Scan Start] ID: {scan_id} | Target: {ip_address} | Type: {scan_type}")

    try:
        proxy = get_proxy_by_id(proxy_id)
        if not proxy:
            raise Exception(f"Proxy with ID {proxy_id} not found or inactive")

        print(f"[Proxy Selected] {proxy.ip_address}:{proxy.port}")

        # Setup proxy with proper error handling
        if not setup_socks5_proxy(proxy):
            raise Exception("Failed to setup proxy connection")

        results_str = ""

        if scan_type == 'port_scan':
            open_ports = []
            for port in [21, 22, 80, 443, 3389]:  # Common ports for testing
                try:
                    s = socks.socksocket()
                    s.settimeout(3)  # Increased timeout for proxy connections
                    s.connect((ip_address, port))
                    open_ports.append(str(port))
                    s.close()
                except Exception as e:
                    print(f"Port {port} closed or error: {str(e)}")
                    continue
            results_str = "Open Ports: " + ", ".join(open_ports) if open_ports else "No open ports found"

        elif scan_type == 'hostname_scan':
            try:
                # With SOCKS5, we need to ensure remote DNS is used
                socks.set_default_proxy(socks.SOCKS5, proxy.ip_address, proxy.port, rdns=True)
                socket.socket = socks.socksocket
                resolved_hostname = socket.gethostbyaddr(ip_address)
                results_str = f"Resolved Hostname: {resolved_hostname[0]}"
            except socket.herror as e:
                results_str = f"Hostname resolution failed: {e}"
            except Exception as e:
                results_str = f"Error during hostname resolution: {e}"

        else:
            results_str = "Unknown scan type."

        print(f"[Scan Results] Scan ID: {scan_id} | Results: {results_str}")

        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Completed'
            scan.results = results_str
            db.session.commit()

        print(f"[Scan Completed] ID: {scan_id} | Status: Completed\n")

    except Exception as e:
        error_message = f"Scan failed due to: {str(e)}"
        print(f"[Error] {error_message}")
        with db.session.begin():
            scan = Scan.query.get(scan_id)
            scan.status = 'Failed'
            scan.results = error_message
            db.session.commit()
    finally:
        # Always reset proxy settings after scan
        socks.set_default_proxy()
        socket.socket = socket._socketobject
