import requests
import re
from flask import Blueprint, render_template, request, redirect, url_for
import pymysql
from datetime import datetime

# Blueprint setup
proxies_bp = Blueprint('proxies', __name__)

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

import struct
# Function to insert proxies into the DB
def insert_proxies_into_db(proxies):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            for proxy in proxies:
                cursor.execute("INSERT INTO proxies (ip_address, port, status, type, last_scanned) VALUES (%s, %s, %s, %s, %s)",
                               (proxy['ip'], proxy['port'], 'unknown', proxy['type'], datetime.now()))
        connection.commit()
    finally:
        connection.close()

# Function to parse the proxies
def parse_proxies(proxy_list_text):
    proxies = []
    # Regex pattern for IPv4 proxies with port
    proxy_pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)'
    matches = re.findall(proxy_pattern, proxy_list_text)

    for match in matches:
        ip_address = match[0]
        port = match[1]
        # For simplicity, assuming SOCKS5 as proxy type. Modify as necessary.
        proxy = {'ip': ip_address, 'port': port, 'type': 'SOCKS5'}
        proxies.append(proxy)

    return proxies

# Function to scrape proxies from the URL
def scrape_proxies(url):
    print(f"Scraping proxies from: {url}")
    proxies = []

    try:
        # Fetch raw proxy list content
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully scraped URL: {url}")
            proxies = parse_proxies(response.text)
            print(f"Found {len(proxies)} proxies.")

            # Now, insert the proxies into the database
            insert_proxies_into_db(proxies)
            print("Proxies successfully inserted into the database.")
        else:
            print(f"Failed to scrape URL: {url}, Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")

    return proxies

# Route for proxies page
@proxies_bp.route('/')
def proxies():
    connection = get_db_connection()
    try:
        # Get the current page from the URL query string, default to 1 if not provided
        page = request.args.get('page', 1, type=int)
        limit = 10  # Number of proxies per page
        offset = (page - 1) * limit

        with connection.cursor() as cursor:
            # Fetch proxies with pagination (including type and last scanned)
            cursor.execute("SELECT id, ip_address, port, status, type, last_scanned FROM proxies LIMIT %s OFFSET %s", (limit, offset))
            proxies = cursor.fetchall()

            # Get the total count of proxies for pagination
            cursor.execute("SELECT COUNT(*) FROM proxies")
            total_proxies = cursor.fetchone()[0]

    finally:
        connection.close()

    # Calculate total pages for pagination
    total_pages = (total_proxies // limit) + (1 if total_proxies % limit > 0 else 0)

    return render_template('proxies.html', proxies=proxies, page=page, total_pages=total_pages)

# Route to handle the proxy scraping
@proxies_bp.route('/scan_proxies', methods=['POST'])
def scan_proxies():
    proxy_url = request.form['proxy_url']

    # Validate the URL
    if not proxy_url:
        return redirect(url_for('proxies.proxies'))

    # Scrape the proxies from the provided URL
    scrape_proxies(proxy_url)

    return redirect(url_for('proxies.proxies'))

# Route to check the proxies status (this will be added later for functionality)
import threading

import subprocess
import pymysql
from datetime import datetime

# Function to test if a proxy is alive using hping3 and proxychains
def test_proxy_alive(proxy):
    try:
        # Proxy IP and Port from the database entry
        proxy_ip = proxy['ip_address']
        proxy_port = proxy['port']

        # Use proxychains to route the hping3 traffic through the proxy
        command = f"proxychains hping3 -S -p {proxy_port} -c 1 {proxy_ip}"

        # Run the command and capture the output
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if the result contains a valid response
        if "RTT" in result.stdout.decode():
            return True
        else:
            return False
    except Exception as e:
        print(f"Error testing proxy {proxy['ip_address']}:{proxy['port']}: {e}")
        return False

# Function to check and update proxy status in the database
def check_and_update_proxies():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Fetch all proxies that are not marked as 'inactive'
            cursor.execute("SELECT id, ip_address, port, status FROM proxies WHERE status != 'inactive'")
            proxies = cursor.fetchall()

            # Check each proxy and update the status
            for proxy in proxies:
                proxy_data = {'id': proxy[0], 'ip_address': proxy[1], 'port': proxy[2], 'status': proxy[3]}

                # Test if the proxy is alive
                is_alive = test_proxy_alive(proxy_data)

                # Update the proxy status in the database
                new_status = 'active' if is_alive else 'inactive'
                cursor.execute("UPDATE proxies SET status = %s, last_scanned = %s WHERE id = %s",
                               (new_status, datetime.now(), proxy[0]))
            connection.commit()
    finally:
        connection.close()

# Route to check all proxies' status
@proxies_bp.route('/check_proxies', methods=['POST'])
def check_proxies():
    check_and_update_proxies()
    return redirect(url_for('proxies.proxies'))
# Route to delete dead proxies and reindex IDs
@proxies_bp.route('/delete_dead_proxies', methods=['POST'])
def delete_dead_proxies():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Step 1: Delete all proxies with 'inactive' status
            cursor.execute("DELETE FROM proxies WHERE status = %s", ('dead',))

            # Step 2: Reindex the remaining proxies
            cursor.execute("SET @i := 0;")
            cursor.execute("UPDATE proxies SET id = (@i := @i + 1);")

            # Step 3: Reset the auto-increment value to the next available ID
            cursor.execute("ALTER TABLE proxies AUTO_INCREMENT = 1;")

        connection.commit()
        print("Dead proxies deleted and IDs reindexed successfully.")
    finally:
        connection.close()

    # Redirect to the proxies page to see the updated proxies and pagination
    return redirect(url_for('proxies.proxies'))
