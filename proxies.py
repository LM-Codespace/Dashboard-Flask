from flask import Blueprint, render_template, request, redirect, url_for
import pymysql

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

@proxies_bp.route('/')
def proxies():
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM proxies")
            proxies_data = cursor.fetchall()
            return render_template('proxies.html', proxies=proxies_data)
    return redirect(url_for('auth.login'))

@proxies_bp.route('/add', methods=['GET', 'POST'])
def add_proxy():
    if 'loggedin' in session:
        connection = get_db_connection()
        if request.method == 'POST':
            ip_address = request.form['ip_address']
            port = request.form['port']
            proxy_type = request.form['type']
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO proxies (ip_address, port, type) VALUES (%s, %s, %s)", 
                               (ip_address, port, proxy_type))
                connection.commit()
            flash('Proxy added successfully!')
            return redirect(url_for('proxies.proxies'))
        return render_template('add_proxy.html')
    return redirect(url_for('auth.login'))

@proxies_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_proxy(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM proxies WHERE id=%s", (id,))
            proxy_data = cursor.fetchone()
            if request.method == 'POST':
                ip_address = request.form['ip_address']
                port = request.form['port']
                proxy_type = request.form['type']
                cursor.execute("UPDATE proxies SET ip_address=%s, port=%s, type=%s WHERE id=%s", 
                               (ip_address, port, proxy_type, id))
                connection.commit()
                flash('Proxy updated successfully!')
                return redirect(url_for('proxies.proxies'))
            return render_template('edit_proxy.html', proxy=proxy_data)
    return redirect(url_for('auth.login'))

@proxies_bp.route('/delete/<int:id>')
def delete_proxy(id):
    if 'loggedin' in session:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM proxies WHERE id=%s", (id,))
            connection.commit()
        flash('Proxy deleted successfully!')
        return redirect(url_for('proxies.proxies'))
    return redirect(url_for('auth.login'))
