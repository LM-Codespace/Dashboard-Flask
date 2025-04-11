from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False, unique=True)  # Unique IP address
    resolved_hostname = db.Column(db.String(100), nullable=True)  # Store resolved hostname (DNS)
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
    __tablename__ = 'scan'  # Explicitly defining the table name
    id = db.Column(db.Integer, primary_key=True)  # Unique scan ID
    date = db.Column(db.DateTime, default=datetime.utcnow)  # Date when scan was run
    status = db.Column(db.String(50))  # Status of the scan (e.g., 'In Progress', 'Completed')
    scan_type = db.Column(db.String(50))  # Type of the scan (e.g., 'hostname', 'port_check')
    host_id = db.Column(db.Integer, db.ForeignKey('host.id'), nullable=False)  # Foreign key reference to Host
    host = db.relationship('Host', backref=db.backref('scans', lazy=True))  # Establishing a relationship to the Host

    def __repr__(self):
        return f'<Scan {self.id}>'
