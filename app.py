from flask import Flask, session, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
import logging
from auth import auth_bp
from hosts import hosts_bp
from proxies import proxies_bp
from scans import scans_bp
from models import db, Host, Proxies  # Import models needed for scans

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'

    # DB configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:flaskpassword@localhost/flask_dashboard'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize db with the app
    db.init_app(app)

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

    # Remove this duplicate route - it's already handled by scans_bp
    # @app.route('/scans')
    # def scans():
    #     return render_template('scans.html')

    return app

# Initialize app
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
