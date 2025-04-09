from flask import Flask, render_template, request, redirect, url_for, session, flash
import ipaddress
import csv
from io import TextIOWrapper
import threading
import pymysql
import logging
from datetime import datetime

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
                # Check if host already exists
                cursor.execute('SELECT id FROM hosts WHERE ip_address=%s', (str(ip),))
                if cursor.fetchone() is None:
                    cursor.execute(
                        'INSERT INTO hosts (hostname, ip_address, os) VALUES (%s, %s, %s)',
                        (hostname, str(ip), os)
                    )
                    added += 1
                else:
                    skipped += 1
                current += 1
            except pymysql.Error as e:
                logger.error(f"Database error for {ip}: {e}")
                skipped += 1
                continue
                
        connection.commit()
        logger.info(f"Completed range: {start_ip}-{end_ip} (Added: {added}, Skipped: {skipped})")
        
    except (ipaddress.AddressValueError, ValueError) as e:
        logger.error(f"Invalid IP range {start_ip}-{end_ip}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing {start_ip}-{end_ip}: {e}")
    finally:
        cursor.close()
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
                cursor.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password))
                account = cursor.fetchone()
                if account:
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
    if 'loggedin' in session:
        connection = get_db_connection()
        try:
            if request.method == 'POST':
                if 'hostname' in request.form:
                    hostname = request.form['hostname']
                    ip_address = request.form['ip_address']
                    os = request.form['os']

                    with connection.cursor() as cursor:
                        cursor.execute('INSERT INTO hosts (hostname, ip_address, os) VALUES (%s, %s, %s)',
                                     (hostname, ip_address, os))
                        connection.commit()
                        flash('Host added successfully!', 'success')
                        return redirect(url_for('hosts'))

            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM hosts')
                hosts = cursor.fetchall()
                return render_template('hosts.html', title="Hosts", hosts=hosts)
        finally:
            connection.close()
    return redirect(url_for('login'))

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
        # Read and validate CSV
        stream = TextIOWrapper(csv_file.stream, encoding='utf-8')
        reader = csv.reader(stream)
        
        valid_ranges = []
        invalid_lines = 0
        
        for i, row in enumerate(reader, 1):
            if len(row) < 2:
                invalid_lines += 1
                continue
                
            start_ip, end_ip = row[0].strip(), row[1].strip()
            
            try:
                # Validate IP format
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

        # Process ranges in background threads
        for start_ip, end_ip in valid_ranges:
            t = threading.Thread(
                target=process_ip_range,
                args=(start_ip, end_ip, os)
            )
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
        if request.method == 'POST':
            hostname = request.form['hostname']
            ip_address = request.form['ip_address']
            os = request.form['os']

            with connection.cursor() as cursor:
                cursor.execute('UPDATE hosts SET hostname=%s, ip_address=%s, os=%s WHERE id=%s', (hostname, ip_address, os, id))
                connection.commit()
                return redirect(url_for('hosts'))

        # Fetch the host details for editing
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM hosts WHERE id=%s', (id,))
            host = cursor.fetchone()
            return render_template('edit_host.html', title="Edit Host", host=host)
    return redirect(url_for('login'))

@app.route('/hosts/delete/<int:id>')
def delete_host(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM hosts WHERE id=%s', (id,))
            connection.commit()
        return redirect(url_for('hosts'))
    return redirect(url_for('login'))

# View Proxies
@app.route('/proxies')
def proxies():
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM proxies")
            proxies_data = cursor.fetchall()
            return render_template('proxies.html', title="Proxies", proxies=proxies_data)
    return redirect(url_for('login'))

# Add Proxy
@app.route('/proxies/add', methods=['GET', 'POST'])
def add_proxy():
    if 'loggedin' in session:
        connection = get_db_connection()
        if request.method == 'POST':
            ip_address = request.form['ip_address']
            port = request.form['port']
            type = request.form['type']
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO proxies (ip_address, port, type) VALUES (%s, %s, %s)", (ip_address, port, type))
                connection.commit()
            return redirect(url_for('proxies'))
        return render_template('add_proxy.html', title="Add Proxy")
    return redirect(url_for('login'))

# Edit Proxy
@app.route('/proxies/edit/<int:id>', methods=['GET', 'POST'])
def edit_proxy(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM proxies WHERE id=%s", (id,))
            proxy_data = cursor.fetchone()
            if request.method == 'POST':
                ip_address = request.form['ip_address']
                port = request.form['port']
                type = request.form['type']
                cursor.execute("UPDATE proxies SET ip_address=%s, port=%s, type=%s WHERE id=%s", (ip_address, port, type, id))
                connection.commit()
                return redirect(url_for('proxies'))
            return render_template('edit_proxy.html', title="Edit Proxy", proxy=proxy_data)
    return redirect(url_for('login'))

# Delete Proxy
@app.route('/proxies/delete/<int:id>')
def delete_proxy(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM proxies WHERE id=%s", (id,))
            connection.commit()
        return redirect(url_for('proxies'))
    return redirect(url_for('login'))

@app.route('/scan_proxies')
def scan_proxies():
    # Your code to handle proxy scanning here
    return "Scanning proxies..."


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
