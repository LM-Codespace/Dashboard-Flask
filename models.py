from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

# Initialize SQLAlchemy object
db = SQLAlchemy()

class StatusEnum(Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    PENDING = "Pending"

class Host(db.Model):
    __tablename__ = 'hosts'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    hostname = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    status = db.Column(db.Enum(StatusEnum), default=StatusEnum.ACTIVE, index=True)
    ports = db.Column(db.Text, nullable=True)
    last_scanned = db.Column(db.TIMESTAMP, nullable=True)
    open_ports = db.Column(db.Text, nullable=True)
    resolved_hostname = db.Column(db.Text, nullable=True)
    location = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Host {self.ip_address}>'

    def __str__(self):
        return f"IP: {self.ip_address}, Status: {self.status.name}"

    def __init__(self, ip_address, hostname=None, os=None, status=StatusEnum.ACTIVE, 
                 ports=None, last_scanned=None, open_ports=None, resolved_hostname=None, location=None):
        self.ip_address = ip_address
        self.hostname = hostname
        self.os = os
        self.status = status
        self.ports = ports
        self.last_scanned = last_scanned
        self.open_ports = open_ports
        self.resolved_hostname = resolved_hostname
        self.location = location

class Proxies(db.Model):
    __tablename__ = 'proxies'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False, index=True)
    port = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active', index=True)
    type = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Proxy {self.ip_address}:{self.port}>'

    def __str__(self):
        return f"{self.ip_address}:{self.port} ({self.status})"

class Scan(db.Model):
    __tablename__ = 'scan'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False)
    scan_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'), nullable=True)
    proxy = db.relationship('Proxies', backref=db.backref('scans', lazy=True, passive_deletes=True))
    results = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Scan {self.id} - {self.scan_type}>'

    def __str__(self):
        return f"Scan ID: {self.id}, Type: {self.scan_type}, Status: {self.status}"

