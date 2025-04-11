from flask import Flask, session, redirect, url_for, render_template
import logging
from auth import auth_bp
from hosts import hosts_bp
from proxies import proxies_bp
from flask_sqlalchemy import SQLAlchemy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize db (but don't import it yet)
db = SQLAlchemy()

# Create app factory function
def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'

    # DB configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://flaskuser:flaskpassword@localhost/flask_dashboard'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize db here
    db.init_app(app)

    # Register blueprints
    from scans import scans_bp  # Import scans after creating the app
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

    @app.route('/scans')
    def scans():
        return render_template('scans.html')

    return app

# Initialize app
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
