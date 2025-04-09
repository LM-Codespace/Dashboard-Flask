from flask import Blueprint, render_template, request, redirect, url_for, flash
import pymysql
import threading
import csv
from io import TextIOWrapper
import ipaddress
from datetime import datetime

hosts_bp = Blueprint('hosts', __name__)

# DB connection
def get_db_connection():
    DB_CONFIG = {
        'host': "localhost",
        'user': "flaskuser",
        'passwd': "flaskpassword",
        'db': "flask_dashboard",
        'autocommit': True
    }
    return pymysql.connect(**DB_CONFIG)

# Helper function to process IP range
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
                current += 1
            except pymysql.Error as e:
                skipped += 1
                continue
                
        connection.commit()
    finally:
        cursor.close()
        connection.close()

@hosts_bp.route('/')
def hosts():
    if 'loggedin' in session:
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT * FROM hosts')
                hosts = cursor.fetchall()
                return render_template('hosts.html', hosts=hosts)
        finally:
            connection.close()
    return redirect(url_for('auth.login'))

@hosts_bp.route('/add', methods=['POST'])
def add_host():
    if 'loggedin' in session:
        hostname = request.form['hostname']
        ip_address = request.form['ip_address']
        os = request.form['os']
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO hosts (hostname, ip_address, os) VALUES (%s, %s, %s)', (hostname, ip_address, os))
            connection.commit()
        flash('Host added successfully!')
        return redirect(url_for('hosts.hosts'))
    return redirect(url_for('auth.login'))

@hosts_bp.route('/bulk_csv', methods=['POST'])
def bulk_add_hosts_csv():
    if 'loggedin' not in session:
        flash('Please login first', 'error')
        return redirect(url_for('auth.login'))

    if 'csv_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('hosts.hosts'))

    csv_file = request.files['csv_file']
    os = request.form.get('os', 'Unknown')

    if csv_file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('hosts.hosts'))

    if not csv_file.filename.lower().endswith('.csv'):
        flash('Only CSV files are allowed', 'error')
        return redirect(url_for('hosts.hosts'))

    try:
        # Read and validate CSV
        stream = TextIOWrapper(csv_file.stream, encoding='utf-8')
        reader = csv.reader(stream)
        
        valid_ranges = []
        for row in reader:
            start_ip, end_ip = row[0].strip(), row[1].strip()
            try:
                ipaddress.IPv4Address(start_ip)
                ipaddress.IPv4Address(end_ip)
                valid_ranges.append((start_ip, end_ip))
            except (ipaddress.AddressValueError, ValueError):
                continue

        for start_ip, end_ip in valid_ranges:
            t = threading.Thread(target=process_ip_range, args=(start_ip, end_ip, os))
            t.start()

        flash(f"Started processing {len(valid_ranges)} IP ranges", 'success')
    except Exception as e:
        flash(f'Error processing CSV: {str(e)}', 'error')
    
    return redirect(url_for('hosts.hosts'))

@hosts_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
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
            return redirect(url_for('hosts.hosts'))

        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM hosts WHERE id=%s', (id,))
            host = cursor.fetchone()
            return render_template('edit_host.html', host=host)
    return redirect(url_for('auth.login'))

@hosts_bp.route('/delete/<int:id>')
def delete_host(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM hosts WHERE id=%s', (id,))
            connection.commit()
        flash('Host deleted successfully!')
        return redirect(url_for('hosts.hosts'))
    return redirect(url_for('auth.login'))
