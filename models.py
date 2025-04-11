from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    __tablename__ = 'hosts'  # Ensure this is 'hosts' to match your MySQL table name
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, unique=True)  # Unique IP address
    hostname = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='Active')
    ports = db.Column(db.Text, nullable=True)
    last_scanned = db.Column(db.DateTime, nullable=True)
    open_ports = db.Column(db.Text, nullable=True)
    resolved_hostname = db.Column(db.Text, nullable=True)
    location = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Host {self.ip_address}>'

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
