from flask import Flask, session, redirect, url_for, render_template
import pymysql
import logging
from scans import scans_bp
from auth import auth_bp
from hosts import hosts_bp
from proxies import proxies_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pymysql.install_as_MySQLdb()

# Move the app initialization to a function
def create_app():
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

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(hosts_bp, url_prefix='/hosts')
    app.register_blueprint(proxies_bp, url_prefix='/proxies')
    app.register_blueprint(scans_bp, url_prefix='/scans')

    @app.route('/')
    def home():
        if 'loggedin' in session:
            return redirect(url_for('hosts.hosts'))
        return redirect(url_for('auth.login'))

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/scans')
    def scans():
        return render_template('scans.html')

    return app

# Initialize app
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
