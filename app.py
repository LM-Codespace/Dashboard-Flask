from flask import Flask, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
import logging
import os
from auth import auth_bp
from hosts import hosts_bp
from proxies import proxies_bp
from scans import scans_bp
from models import db, Host, Proxies

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(), logging.FileHandler('app.log', mode='w')])
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

    # DB configuration from environment variable
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'mysql+pymysql://flaskuser:flaskpassword@localhost/flask_dashboard')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize db with the app
    try:
        db.init_app(app)
    except Exception as e:
        logger.error(f"Error initializing the database: {e}")
        raise

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(hosts_bp, url_prefix='/hosts')
    app.register_blueprint(proxies_bp, url_prefix='/proxies')
    app.register_blueprint(scans_bp, url_prefix='/scans')

    # Add the necessary routes
    @app.route('/')
    def home():
        if 'loggedin' in session:
            return redirect(url_for('hosts.hosts'))
        return redirect(url_for('auth.login'))

    @app.route('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    return app

# Initialize app
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
