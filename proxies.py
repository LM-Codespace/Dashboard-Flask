import requests
import re
from flask import Blueprint, render_template, request, redirect, url_for
import pymysql
from datetime import datetime
import subprocess

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

# Function to insert proxies into the DB
def insert_proxies_into_db(proxies):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            for proxy in proxies:
                cursor.execute("""
                    INSERT INTO proxies (ip_address, port, status, type, last_scanned)
                    VALUES (%s, %s, %s, %s, %s)
                """, (proxy['ip'], proxy['port'], 'unknown', proxy['type'], datetime.now()))
        connection.commit()
    finally:
        connection.close()

# Function to parse the proxies
def parse_proxies(proxy_list_text):
    proxies = []
    proxy_pattern = r'(\d+\.\d+\.\d+\.\d+):(\d+)'
    matches = re.findall(proxy_pattern, proxy_list_text)

    for match in matches:
        ip_address, port = match
        proxy = {'ip': ip_address, 'port': port, 'type': 'SOCKS5'}
        proxies.append(proxy)

    return proxies

# Function to scrape proxies from the URL
def scrape_proxies(url):
    print(f"Scraping proxies from: {url}")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Successfully scraped URL: {url}")
            proxies = parse_proxies(response.text)
            print(f"Found {len(proxies)} proxies.")
            insert_proxies_into_db(proxies)
            print("Proxies successfully inserted into the database.")
        else:
            print(f"Failed to scrape URL: {url}, Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error scraping URL {url}: {e}")

# Route for proxies page
@proxies_bp.route('/')
def proxies():
    connection = get_db_connection()
    try:
        page = request.args.get('page', 1, type=int)
        limit = 10
        offset = (page - 1) * limit

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, ip_address, port, status, type, last_scanned
                FROM proxies
                LIMIT %s OFFSET %s
            """, (limit, offset))
            proxies = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM proxies")
            total_proxies = cursor.fetchone()[0]

    finally:
        connection.close()

    total_pages = (total_proxies // limit) + (1 if total_proxies % limit > 0 else 0)
    return render_template('proxies.html', proxies=proxies, page=page, total_pages=total_pages)

# Route to handle proxy scraping
@proxies_bp.route('/scan_proxies', methods=['POST'])
def scan_proxies():
    proxy_url = request.form['proxy_url']
    if not proxy_url:
        return redirect(url_for('proxies.proxies'))

    scrape_proxies(proxy_url)
    return redirect(url_for('proxies.proxies'))

# Function to test if a proxy is alive using hping3 through proxychains
def test_proxy_alive(proxy):
    try:
        proxy_ip = proxy['ip_address']
        proxy_port = proxy['port']
        print(f"Testing proxy: {proxy_ip}:{proxy_port}")

        command = f"proxychains hping3 -S -p {proxy_port} -c 1 {proxy_ip}"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        output = result.stdout.decode()
        print(f"hping3 output for {proxy_ip}:{proxy_port}:\n{output}")

        return "flags=SA" in output or "rtt=" in output
    except Exception as e:
        print(f"Error testing proxy {proxy['ip_address']}:{proxy['port']}: {e}")
        return False


# Function to check and update proxy status
def check_and_update_proxies():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, ip_address, port, status FROM proxies")
            proxies = cursor.fetchall()

            for proxy in proxies:
                proxy_data = {
                    'id': proxy[0],
                    'ip_address': proxy[1],
                    'port': proxy[2],
                    'status': proxy[3]
                }

                is_alive = test_proxy_alive(proxy_data)
                new_status = 'active' if is_alive else 'inactive'

                cursor.execute("""
                    UPDATE proxies
                    SET status = %s, last_scanned = %s
                    WHERE id = %s
                """, (new_status, datetime.now(), proxy_data['id']))
        connection.commit()
    finally:
        connection.close()

# Route to check all proxies' status
@proxies_bp.route('/check_proxies', methods=['POST'])
def check_proxies():
    check_and_update_proxies()
    return redirect(url_for('proxies.proxies'))

@proxies_bp.route('/delete_dead_proxies', methods=['POST'])
def delete_dead_proxies():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # First, set proxy_id to NULL for all scans using the proxy
            cursor.execute("UPDATE scan SET proxy_id = NULL WHERE proxy_id IN (SELECT id FROM proxies WHERE status = %s)", ('inactive',))

            # Now, delete the dead proxies
            cursor.execute("DELETE FROM proxies WHERE status = %s", ('inactive',))
            
            # Reindex the remaining proxies (optional)
            cursor.execute("SET @i := 0;")
            cursor.execute("UPDATE proxies SET id = (@i := @i + 1);")
            cursor.execute("ALTER TABLE proxies AUTO_INCREMENT = 1;")
        
        # Commit changes to the database
        connection.commit()
        print("Dead proxies deleted and IDs reindexed successfully.")
    
    except Exception as e:
        print(f"Error occurred while deleting dead proxies: {e}")
    
    finally:
        connection.close()
    
    return redirect(url_for('proxies.proxies'))
