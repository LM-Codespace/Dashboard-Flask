from flask import Flask, render_template, request, redirect, url_for, session, flash
import pymysql
from pymysql.cursors import DictCursor
import re
import requests
from bs4 import BeautifulSoup
import socket
import concurrent.futures
import time
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key

# Database Configuration
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='your_db_username',
        password='your_db_password',
        database='your_database_name',
        cursorclass=DictCursor
    )

# Initialize Database Tables
def init_db():
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Create hosts table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hosts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ip_address VARCHAR(15) NOT NULL,
                    hostname VARCHAR(255),
                    ports TEXT,
                    last_scanned TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create proxies table if not exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proxies (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    ip_address VARCHAR(15) NOT NULL,
                    port INT NOT NULL,
                    protocol VARCHAR(10) DEFAULT 'socks5',
                    country VARCHAR(2),
                    latency FLOAT,
                    last_checked TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    source_url VARCHAR(255),
                    UNIQUE (ip_address, port)
                )
            ''')
            
            connection.commit()
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()

# Routes
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Add your authentication logic here
        if username == 'admin' and password == 'password':  # Change to real credentials
            session['loggedin'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/hosts', methods=['GET', 'POST'])
def hosts():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        
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

        page = request.args.get('page', 1, type=int)
        per_page = 50
        
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM hosts')
            total = cursor.fetchone()['COUNT(*)']
            offset = (page - 1) * per_page
            
            cursor.execute(
                'SELECT id, ip_address, hostname, ports, last_scanned '
                'FROM hosts ORDER BY last_scanned DESC LIMIT %s OFFSET %s',
                (per_page, offset)
            )
            hosts = cursor.fetchall()
            
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
        return redirect(url_for('dashboard'))
    finally:
        if connection:
            connection.close()


# Proxy Management
@app.route('/proxies')
def proxies():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
    
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT id, ip_address, port, protocol, country, 
                       latency, last_checked, is_active 
                FROM proxies 
                ORDER BY last_checked DESC
            ''')
            proxies = cursor.fetchall()
            
            # Set defaults for any None values
            for proxy in proxies:
                proxy['protocol'] = proxy.get('protocol', 'socks5')
                proxy['is_active'] = proxy.get('is_active', False)
            
        return render_template('proxies.html', proxies=proxies)
    except Exception as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('dashboard'))
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
            save_proxies(working_proxies, urls[0])  # Save with first URL as source
            
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
                is_working, latency = check_socks5_proxy(proxy['ip_address'], proxy['port'])
                
                cursor.execute('''
                    UPDATE proxies 
                    SET is_active = %s, latency = %s, last_checked = CURRENT_TIMESTAMP 
                    WHERE id = %s
                ''', (is_working, latency, id))
                connection.commit()
                
                status = "working" if is_working else "not working"
                flash(f'Proxy {proxy["ip_address"]}:{proxy["port"]} is {status} (latency: {latency:.2f}ms)', 
                      'success' if is_working else 'warning')
    
    except Exception as e:
        flash(f'Check failed: {str(e)}', 'error')
    finally:
        if connection:
            connection.close()
    
    return redirect(url_for('proxies'))

# Utility Functions
def scrape_proxies_from_urls(urls):
    proxy_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b')
    proxies = set()
    
    for url in urls:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            
            found = proxy_pattern.findall(text)
            proxies.update([p for p in found if p.count(':') == 1])
            
        except Exception as e:
            app.logger.error(f"Error scraping {url}: {str(e)}")
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
            s.sendall(b'\x05\x01\x00')  # SOCKS5 handshake
            response = s.recv(2)
            if response == b'\x05\x00':
                latency = (time.time() - start_time) * 1000  # ms
                return True, latency
        return False, 0
    except (socket.timeout, ConnectionRefusedError, socket.error):
        return False, 0

def save_proxies(proxies, source_url=None):
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            for proxy in proxies:
                try:
                    cursor.execute('''
                        INSERT INTO proxies (ip_address, port, protocol, latency, 
                                           last_checked, is_active, source_url)
                        VALUES (%s, %s, 'socks5', %s, CURRENT_TIMESTAMP, TRUE, %s)
                        ON CONFLICT (ip_address, port) 
                        DO UPDATE SET 
                            latency = EXCLUDED.latency,
                            last_checked = EXCLUDED.last_checked,
                            is_active = TRUE,
                            source_url = COALESCE(EXCLUDED.source_url, proxies.source_url)
                    ''', (proxy['ip'], proxy['port'], proxy.get('latency', 0), source_url))
                except Exception as e:
                    app.logger.error(f"Error saving proxy {proxy['ip']}:{proxy['port']}: {str(e)}")
                    continue
        connection.commit()
    except Exception as e:
        app.logger.error(f"Database error saving proxies: {str(e)}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()

if __name__ == '__main__':
    init_db()  # Initialize database tables
    app.run(host='0.0.0.0', port=5000, debug=True)
