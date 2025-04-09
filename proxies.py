from flask import session, Blueprint, render_template, request, redirect, url_for, flash
import pymysql
import requests
import socks
import socket
from bs4 import BeautifulSoup
from ping3 import ping
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

# This is the endpoint you're likely looking for
@proxies_bp.route('/scan_proxies', methods=['POST'])
def scan_proxies():
    url = request.form.get('proxy_url')  # Make sure you're getting the URL correctly from the form
    if url:
        proxies = scrape_proxies(url)
        if proxies:
            print(f"Found {len(proxies)} proxies to add.")
            # Save proxies to the database
            connection = get_db_connection()
            with connection.cursor() as cursor:
                for proxy in proxies:
                    ip, port = proxy
                    cursor.execute("INSERT INTO proxies (ip_address, port, status) VALUES (%s, %s, %s)",
                                   (ip, port, 'UNKNOWN'))  # Initially set status as 'UNKNOWN'
                connection.commit()
            flash(f"{len(proxies)} proxies scraped and added!")
        else:
            flash("No proxies found on the provided URL.")
    return redirect(url_for('proxies.proxies'))

# Scrape proxy list (IP:PORT) from a URL
def scrape_proxies_from_url(url):
    proxies = []
    try:
        print(f"Scraping URL: {url}")
        response = requests.get(url)
        print(f"Response status code: {response.status_code}")

        if response.status_code != 200:
            print(f"Failed to fetch URL {url}, Status code: {response.status_code}")
            return proxies

        # For raw text files, we assume each line contains a proxy in the format 'IP:PORT'
        # Example: '192.168.1.1:8080'
        proxy_list = response.text.splitlines()
        
        for proxy in proxy_list:
            if ':' in proxy:  # Ensure it's in the IP:PORT format
                proxies.append(proxy.strip())

        if not proxies:
            print("No proxies found on this URL.")
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    
    return proxies


# Add proxy to the database
def add_proxy_to_db(proxy):
    ip, port = proxy.split(":")
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO proxies (ip_address, port, type) VALUES (%s, %s, %s)",
                       (ip, port, 'SOCKS5'))
        connection.commit()

def check_proxy(ip_address, port):
    try:
        # Ping the IP address (check if the server is reachable)
        ping_response = ping(ip_address, timeout=3)
        if ping_response is None:
            print(f"Proxy {ip_address} is not reachable via ping.")
            return False

        # Check if the port is open (proxy is listening)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex((ip_address, port))
        if result == 0:
            return True
        else:
            print(f"Proxy {ip_address}:{port} is not listening on the port.")
            return False
    except Exception as e:
        print(f"Error checking proxy {ip_address}:{port} - {e}")
        return False


@proxies_bp.route('/check_proxies', methods=['POST'])
def check_proxies():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM proxies")
        proxies_data = cursor.fetchall()

        for proxy in proxies_data:
            ip, port = proxy[1], proxy[2]  # Assuming columns [id, ip_address, port]
            if check_proxy(ip, port):  # Using the new check_proxy function
                cursor.execute("UPDATE proxies SET status = 'LIVE' WHERE id = %s", (proxy[0],))
            else:
                cursor.execute("UPDATE proxies SET status = 'DEAD' WHERE id = %s", (proxy[0],))
        
        connection.commit()

    flash("Proxies checked successfully!")
    return redirect(url_for('proxies.proxies'))


# Delete dead proxies
@proxies_bp.route('/delete_dead_proxies', methods=['POST'])
def delete_dead_proxies():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM proxies WHERE status = 'DEAD'")
        connection.commit()

    flash("Dead proxies have been deleted!")
    return redirect(url_for('proxies.proxies'))


# View proxies
@proxies_bp.route('/')
def proxies():
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM proxies")
            proxies_data = cursor.fetchall()
            return render_template('proxies.html', proxies=proxies_data)
    return redirect(url_for('auth.login'))
