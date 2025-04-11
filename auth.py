from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)

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

# Login Required Decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'loggedin' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrap

@auth_bp.route('/', methods=['GET', 'POST'])
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
                    return redirect(url_for('hosts.hosts'))  # Redirect to hosts page
                else:
                    msg = 'Incorrect username/password!'
        finally:
            connection.close()
    return render_template('login.html', msg=msg)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", 'info')  # Logout message
    return redirect(url_for('auth.login'))

# Example of protecting another route with login_required
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

