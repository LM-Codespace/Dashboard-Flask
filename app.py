from flask import Flask, render_template, request, redirect, url_for, session, flash
import ipaddress
import csv
import threading
import logging
import psycopg2
import re
import socket
import time
from datetime import datetime
from io import TextIOWrapper
from werkzeug.security import check_password_hash
from bs4 import BeautifulSoup
import requests
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database configuration
DB_CONFIG = {
    'host': "localhost",
    'user': "flaskuser",
    'password': "flaskpassword",
    'dbname': "flask_dashboard"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

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

def is_valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def scan_port(ip, port, timeout=1.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except:
        return False

def validate_proxy(ip, port):
    if not is_valid_ip(ip) or not (0 < int(port) < 65536):
        return False
    return scan_port(ip, int(port))

def extract_proxies_from_text(text):
    proxies = []
    lines = text.strip().split('\n')
    for line in lines:
        parts = re.split(r'[:\s,]', line.strip())
        if len(parts) >= 2 and is_valid_ip(parts[0]) and parts[1].isdigit():
            proxies.append({'ip': parts[0], 'port': parts[1]})
    return proxies

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        uploaded_file = request.files['file']
        if uploaded_file.filename.endswith('.csv'):
            stream = TextIOWrapper(uploaded_file.stream, encoding='utf-8')
            reader = csv.reader(stream)
            proxies = []
            for row in reader:
                if len(row) >= 2 and is_valid_ip(row[0]) and row[1].isdigit():
                    proxies.append({'ip': row[0], 'port': row[1]})
            save_proxies(proxies)
            flash(f'Successfully uploaded and saved {len(proxies)} proxies.')
        else:
            flash('Please upload a CSV file.')
        return redirect(url_for('upload'))

    return render_template('upload.html')

@app.route('/scrape', methods=['GET', 'POST'])
def scrape():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        url = request.form['url']
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()
            proxies = extract_proxies_from_text(text)
            save_proxies(proxies)
            flash(f'Successfully scraped and saved {len(proxies)} proxies.')
        except Exception as e:
            flash(f'Failed to scrape proxies: {str(e)}')

        return redirect(url_for('scrape'))

    return render_template('scrape.html')

@app.route('/proxies')
def view_proxies():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT ip_address, port, latency, last_checked, is_active FROM proxies ORDER BY last_checked DESC")
    proxies = cursor.fetchall()
    cursor.close()
    connection.close()
    return render_template('proxies.html', proxies=proxies)

@app.route('/validate', methods=['GET', 'POST'])
def validate():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT ip_address, port FROM proxies")
    all_proxies = cursor.fetchall()
    cursor.close()
    connection.close()

    valid_proxies = []

    def check_and_update(proxy):
        ip, port = proxy
        if validate_proxy(ip, port):
            valid_proxies.append({'ip': ip, 'port': port, 'latency': 0})
        else:
            # Mark as inactive
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("UPDATE proxies SET is_active = FALSE WHERE ip_address = %s AND port = %s", (ip, port))
            conn.commit()
            cur.close()
            conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(check_and_update, all_proxies)

    save_proxies(valid_proxies)
    flash(f'Validation complete. {len(valid_proxies)} proxies are active.')
    return redirect(url_for('view_proxies'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and request.form['password'] == 'admin':
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged out successfully.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
