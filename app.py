from flask import Flask, render_template, request, redirect, url_for, session, flash
import ipaddress
import csv
from io import TextIOWrapper
import threading
import pymysql
import logging
from datetime import datetime
from werkzeug.security import check_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# DB configuration
DB_CONFIG = {
    'host': "localhost",
    'user': "flaskuser",
    'passwd': "flaskpassword",
    'db': "flask_dashboard",
    'autocommit': True
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def process_ip_range(start_ip, end_ip, os):
    connection = get_db_connection()
    cursor = connection.cursor()
    added = 0
    skipped = 0

    try:
        start = ipaddress.IPv4Address(start_ip)
        end = ipaddress.IPv4Address(end_ip)
        current = int(start)
        end_int = int(end)

        logger.info(f"Processing range: {start_ip} to {end_ip}")

        while current <= end_int:
            ip = ipaddress.IPv4Address(current)
            hostname = f"host-{str(ip).replace('.', '-')}-{datetime.now().strftime('%Y%m%d')}"

            try:
                cursor.execute('SELECT id FROM hosts WHERE ip_address=%s', (str(ip),))
                if cursor.fetchone() is None:
                    cursor.execute(
                        'INSERT INTO hosts (hostname, ip_address, os) VALUES (%s, %s, %s)',
                        (hostname, str(ip), os)
                    )
                    added += 1
                else:
                    skipped += 1
            except pymysql.Error as e:
                logger.error(f"Database error for {ip}: {e}")
                skipped += 1
            finally:
                current += 1

        connection.commit()
        logger.info(f"Completed range: {start_ip}-{end_ip} (Added: {added}, Skipped: {skipped})")

    except (ipaddress.AddressValueError, ValueError) as e:
        logger.error(f"Invalid IP range {start_ip}-{end_ip}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing {start_ip}-{end_ip}: {e}")
    finally:
        cursor.close()
        connection.close()

@app.route('/hosts/scan/<int:id>')
def scan_host(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Get host information
            cursor.execute('SELECT ip_address FROM hosts WHERE id = %s', (id,))
            host = cursor.fetchone()
            
            if not host:
                flash('Host not found', 'error')
                return redirect(url_for('hosts'))
            
            ip_address = host[0]
            
            # Here you would implement your actual port scanning logic
            # For now, we'll simulate a scan with common ports
            scanned_ports = "22,80,443"  # Replace with actual scan results
            last_scanned = datetime.now()
            
            # Update the host record
            cursor.execute(
                'UPDATE hosts SET ports = %s, last_scanned = %s WHERE id = %s',
                (scanned_ports, last_scanned, id)
            )
            connection.commit()
            
            flash(f'Port scan completed for {ip_address}', 'success')
            return redirect(url_for('hosts'))
            
    except Exception as e:
        flash(f'Scan failed: {str(e)}', 'error')
        app.logger.error(f'Scan failed for host {id}: {str(e)}')
        return redirect(url_for('hosts'))
    finally:
        if connection:
            connection.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username=%s', (username,))
                account = cursor.fetchone()
                if account and check_password_hash(account[2], password):
                    session['loggedin'] = True
                    session['username'] = account[1]
                    return redirect(url_for('dashboard'))
                else:
                    msg = 'Incorrect username/password!'
        finally:
            connection.close()
    return render_template('login.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('dashboard.html', username=session['username'], title="Dashboard")
    return redirect(url_for('login'))

@app.route('/scans')
def scans():
    if 'loggedin' in session:
        return render_template('scans.html', title="Scans")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/hosts', methods=['GET', 'POST'])
def hosts():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        
        # Handle POST request
        if request.method == 'POST' and 'ip_address' in request.form:
            ip_address = request.form['ip_address']
            hostname = request.form.get('hostname', '')
            ports = request.form.get('ports', '')
            
            with connection.cursor() as cursor:
                cursor.execute(
                    'INSERT INTO hosts (ip_address, hostname, ports, last_scanned) '
                    'VALUES (%s, %s, %s, CURRENT_TIMESTAMP)',
                    (ip_address, hostname, ports)
                )
                connection.commit()
                flash('Host added successfully!', 'success')
                return redirect(url_for('hosts'))

        # Handle GET request
        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        with connection.cursor() as cursor:
            # Get total count
            cursor.execute('SELECT COUNT(*) FROM hosts')
            total = cursor.fetchone()[0]
            
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Fetch paginated results
            cursor.execute(
                'SELECT id, ip_address, hostname, ports, last_scanned '
                'FROM hosts ORDER BY last_scanned DESC LIMIT %s OFFSET %s',
                (per_page, offset)
            )
            
            # Convert tuples to dictionaries manually
            columns = ['id', 'ip_address', 'hostname', 'ports', 'last_scanned']
            hosts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            pages = (total + per_page - 1) // per_page
            
            return render_template(
                'hosts.html',
                hosts=hosts,
                pagination={
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': pages,
                    'has_prev': page > 1,
                    'has_next': page < pages
                }
            )
            
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        app.logger.error(f'Database error in hosts route: {str(e)}')
        return redirect(url_for('hosts'))
        
    finally:
        if connection:
            connection.close()
            
@app.route('/hosts/bulk_csv', methods=['POST'])
def bulk_add_hosts_csv():
    if 'loggedin' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('login'))

    if 'csv_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('hosts'))

    csv_file = request.files['csv_file']
    os = request.form.get('os', 'Unknown')

    if csv_file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('hosts'))

    if not csv_file.filename.lower().endswith('.csv'):
        flash('Only CSV files are allowed', 'error')
        return redirect(url_for('hosts'))

    try:
        stream = csv_file.stream.read().decode('utf-8').splitlines()
        reader = csv.reader(stream)


        valid_ranges = []
        invalid_lines = 0

        for i, row in enumerate(reader, 1):
            if len(row) < 2:
                invalid_lines += 1
                continue

            start_ip, end_ip = row[0].strip(), row[1].strip()

            try:
                ipaddress.IPv4Address(start_ip)
                ipaddress.IPv4Address(end_ip)
                valid_ranges.append((start_ip, end_ip))
            except (ipaddress.AddressValueError, ValueError):
                invalid_lines += 1
                logger.warning(f"Invalid IP format in line {i}: {row}")

        if invalid_lines > 0:
            flash(f"Ignored {invalid_lines} invalid lines in CSV", 'warning')

        if not valid_ranges:
            flash('No valid IP ranges found in CSV', 'error')
            return redirect(url_for('hosts'))

        for start_ip, end_ip in valid_ranges:
            t = threading.Thread(target=process_ip_range, args=(start_ip, end_ip, os))
            t.start()

        flash(f"Started processing {len(valid_ranges)} IP ranges in background", 'success')

    except Exception as e:
        logger.exception("Failed to process CSV upload")
        flash(f'Error processing CSV: {str(e)}', 'error')

    return redirect(url_for('hosts'))

@app.route('/hosts/edit/<int:id>', methods=['GET', 'POST'])
def edit_host(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                if request.method == 'POST':
                    hostname = request.form['hostname']
                    ip_address = request.form['ip_address']
                    os = request.form['os']

                    cursor.execute(
                        'UPDATE hosts SET hostname=%s, ip_address=%s, os=%s WHERE id=%s',
                        (hostname, ip_address, os, id)
                    )
                    connection.commit()
                    return redirect(url_for('hosts'))

                cursor.execute('SELECT * FROM hosts WHERE id=%s', (id,))
                host = cursor.fetchone()
                return render_template('edit_host.html', title="Edit Host", host=host)
        finally:
            connection.close()
    return redirect(url_for('login'))

@app.route('/hosts/delete/<int:id>')
def delete_host(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM hosts WHERE id=%s', (id,))
                connection.commit()
        finally:
            connection.close()
        return redirect(url_for('hosts'))
    return redirect(url_for('login'))

@app.route('/proxies')
def proxies():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # First check if the table has all columns
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'proxies'
            """)
            existing_columns = {row[0] for row in cursor.fetchall()}
            
            # Build query based on available columns
            columns = []
            if 'protocol' in existing_columns:
                columns.append('protocol')
            if 'country' in existing_columns:
                columns.append('country')
            if 'latency' in existing_columns:
                columns.append('latency')
            if 'last_checked' in existing_columns:
                columns.append('last_checked')
            if 'is_active' in existing_columns:
                columns.append('is_active')
            
            base_columns = 'id, ip_address, port'
            additional_columns = ', ' + ', '.join(columns) if columns else ''
            
            cursor.execute(f'''
                SELECT {base_columns}{additional_columns}
                FROM proxies 
                ORDER BY last_checked DESC NULLS FIRST
            ''')
            
            # Create dictionary results
            column_names = ['id', 'ip_address', 'port'] + columns
            proxies = [dict(zip(column_names, row)) for row in cursor.fetchall()]
            
            # Set default values for missing columns
            for proxy in proxies:
                proxy.setdefault('protocol', 'socks5')
                proxy.setdefault('country', None)
                proxy.setdefault('latency', None)
                proxy.setdefault('last_checked', None)
                proxy.setdefault('is_active', True)
            
        return render_template('proxies.html', proxies=proxies)
        
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        app.logger.error(f'Database error in proxies route: {str(e)}')
        return redirect(url_for('dashboard'))  # Redirect to dashboard instead of index
    finally:
        if connection:
            connection.close()

@app.route('/proxies/scan', methods=['GET', 'POST'])
def scan_proxies():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        urls = request.form.get('urls', '').split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        
        if not urls:
            flash('Please provide at least one URL', 'error')
            return redirect(url_for('scan_proxies'))
        
        try:
            found_proxies = scrape_proxies_from_urls(urls)
            working_proxies = check_proxies(found_proxies)
            save_proxies(working_proxies)
            
            flash(f'Found {len(found_proxies)} proxies, {len(working_proxies)} working', 'success')
        except Exception as e:
            flash(f'Scan failed: {str(e)}', 'error')
        
        return redirect(url_for('proxies'))
    
    return render_template('scan_proxies.html')

@app.route('/proxies/check/<int:id>')
def check_proxy(id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT ip_address, port FROM proxies WHERE id = %s', (id,))
            proxy = cursor.fetchone()
            
            if proxy:
                ip, port = proxy
                is_working, latency = check_socks5_proxy(ip, port)
                
                cursor.execute('''
                    UPDATE proxies 
                    SET is_active = %s, latency = %s, last_checked = CURRENT_TIMESTAMP 
                    WHERE id = %s
                ''', (is_working, latency, id))
                connection.commit()
                
                status = "working" if is_working else "not working"
                flash(f'Proxy {ip}:{port} is {status} (latency: {latency:.2f}ms)', 'success' if is_working else 'warning')
    
    except Exception as e:
        flash(f'Check failed: {str(e)}', 'error')
    finally:
        if connection:
            connection.close()
    
    return redirect(url_for('proxies'))

def scrape_proxies_from_urls(urls):
    proxy_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b')
    proxies = set()
    
    for url in urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            found = proxy_pattern.findall(text)
            proxies.update([p for p in found if p.count(':') == 1])
            
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            continue
    
    return [{'ip': p.split(':')[0], 'port': int(p.split(':')[1])} for p in proxies]

def check_proxies(proxies, timeout=5):
    working_proxies = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {
            executor.submit(check_socks5_proxy, proxy['ip'], proxy['port'], timeout): proxy 
            for proxy in proxies
        }
        
        for future in concurrent.futures.as_completed(futures):
            proxy = futures[future]
            try:
                is_working, latency = future.result()
                if is_working:
                    proxy['latency'] = latency
                    working_proxies.append(proxy)
            except Exception:
                continue
    
    return working_proxies

def check_socks5_proxy(ip, port, timeout=5):
    try:
        start_time = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
            # Basic SOCKS5 handshake
            s.sendall(b'\x05\x01\x00')
            response = s.recv(2)
            if response == b'\x05\x00':
                latency = (time.time() - start_time) * 1000  # in milliseconds
                return True, latency
        return False, 0
    except (socket.timeout, ConnectionRefusedError, socket.error):
        return False, 0

def save_proxies(proxies):
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            for proxy in proxies:
                try:
                    cursor.execute('''
                        INSERT INTO proxies (ip_address, port, protocol, latency, last_checked, is_active)
                        VALUES (%s, %s, 'socks5', %s, CURRENT_TIMESTAMP, TRUE)
                        ON CONFLICT (ip_address, port) 
                        DO UPDATE SET 
                            latency = EXCLUDED.latency,
                            last_checked = EXCLUDED.last_checked,
                            is_active = TRUE
                    ''', (proxy['ip'], proxy['port'], proxy.get('latency', 0)))
                except Exception as e:
                    print(f"Error saving proxy {proxy['ip']}:{proxy['port']}: {str(e)}")
                    continue
        connection.commit()
    except Exception as e:
        print(f"Database error: {str(e)}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
