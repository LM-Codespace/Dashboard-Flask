from flask import session, Blueprint, render_template, request, redirect, url_for, flash
import pymysql
import requests
import socks
import socket
from bs4 import BeautifulSoup

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
@proxies_bp.route('/scan_proxies', methods=['GET', 'POST'])
def scan_proxies():
    if request.method == 'POST':
        urls = request.form['urls'].splitlines()  # List of URLs entered by the user
        proxies_list = []
        
        # Scrape the IP:PORT list from the provided URLs
        for url in urls:
            proxies_list.extend(scrape_proxies_from_url(url))

        # Add scraped proxies to the database
        for proxy in proxies_list:
            add_proxy_to_db(proxy)

        flash(f'Found {len(proxies_list)} proxies and added them to the database.')
        return redirect(url_for('proxies.proxies'))

    return render_template('scan_proxies.html')


# Scrape proxy list (IP:PORT) from a URL
def scrape_proxies_from_url(url):
    proxies = []
    try:
        # Fetch the page content
        print(f"Scraping URL: {url}")  # Debug log
        response = requests.get(url)
        print(f"Response status code: {response.status_code}")  # Debug log

        if response.status_code != 200:
            print(f"Failed to fetch URL {url}, Status code: {response.status_code}")
            return proxies

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Example: Find proxies in a table or list
        # Modify this part to suit the actual structure of the page you're scraping
        for row in soup.find_all('tr'):  # Assuming proxies are in rows
            cols = row.find_all('td')
            if len(cols) >= 2:
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                proxy = f'{ip}:{port}'
                print(f"Found proxy: {proxy}")  # Debug log
                proxies.append(proxy)

        if not proxies:
            print("No proxies found on this URL.")  # Debug log
    except Exception as e:
        print(f"Error scraping {url}: {e}")  # Log the error
    return proxies


# Add proxy to the database
def add_proxy_to_db(proxy):
    ip, port = proxy.split(":")
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO proxies (ip_address, port, type) VALUES (%s, %s, %s)",
                       (ip, port, 'SOCKS5'))
        connection.commit()


# Check if a proxy is live
def check_proxy(ip, port):
    try:
        socks.set_default_proxy(socks.SOCKS5, ip, int(port))
        socket.socket = socks.socksocket  # Monkey patch socket to route through SOCKS5
        response = requests.get('http://httpbin.org/ip', timeout=5)  # Test if proxy is working
        return response.status_code == 200
    except Exception as e:
        print(f"Proxy {ip}:{port} failed: {e}")
        return False


# Check proxies for being live and update their status
@proxies_bp.route('/check_proxies', methods=['POST'])
def check_proxies():
    connection = get_db_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM proxies")
        proxies_data = cursor.fetchall()

        for proxy in proxies_data:
            ip, port = proxy[1], proxy[2]  # Assuming columns [id, ip_address, port]
            if check_proxy(ip, port):
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
