from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(50), nullable=False)
    hostname = db.Column(db.String(100))
    os = db.Column(db.String(100))
    status = db.Column(db.String(50), default='Active')
    ports = db.Column(db.Text)
    last_scanned = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    open_ports = db.Column(db.Text)
    resolved_hostname = db.Column(db.Text)
    location = db.Column(db.Text)

    def __repr__(self):
        return f'<Host {self.hostname} ({self.ip_address})>'

class Proxies(db.Model):
    __tablename__ = 'proxies'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    type = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Proxy {self.ip_address}:{self.port}>'

class Scan(db.Model):
    __tablename__ = 'scan'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    scan_type = db.Column(db.String(50))
    
    # Column for storing the target IP address for the scan
    ip_address = db.Column(db.String(50), nullable=False)
    
    # Proxy reference to associate a proxy with this scan
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'), nullable=True)
    proxy = db.relationship('Proxies', backref=db.backref('scans', lazy=True))

    # Add this column to store the results of the scan (e.g., open ports, hostnames, etc.)
    results = db.Column(db.Text, nullable=True)  # Store scan results (e.g., open ports, hostnames, etc.)
    
    def __repr__(self):
        return f'<Scan {self.id} - {self.scan_type}>'
