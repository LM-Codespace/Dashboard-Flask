from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    __tablename__ = 'hosts'  # Ensure this is 'hosts' to match your MySQL table name
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, unique=True)  # Unique IP address
    resolved_hostname = db.Column(db.String(100), nullable=True)
    open_ports = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Host {self.ip_address}>'



class Proxies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False)  # Store proxy IP address
    port = db.Column(db.Integer, nullable=False)  # Store proxy port number
    status = db.Column(db.String(50), nullable=False)  # Status of the proxy (active, inactive, etc.)
    type = db.Column(db.String(50), nullable=False)  # Proxy type (e.g., 'SOCKS5')

    def __repr__(self):
        return f'<Proxy {self.ip_address}:{self.port}>'


class Scan(db.Model):
    __tablename__ = 'scan'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))  # e.g., 'In Progress', 'Completed'
    scan_type = db.Column(db.String(50))  # Type of scan (e.g., 'port_scan', 'hostname_scan')
    ip_address = db.Column(db.String(50))  # Store the IP address
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'), nullable=True)  # Reference to Proxies (corrected table name)
    proxy = db.relationship('Proxies', backref=db.backref('scans', lazy=True))  # Corrected relationship

    def __repr__(self):
        return f'<Scan {self.id}>'
