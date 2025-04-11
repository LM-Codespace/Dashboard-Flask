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
    
    # Either add this column to your database or remove it from the model
    # Option 1: Add column to database (recommended)
    # Run: ALTER TABLE scan ADD COLUMN ip_address VARCHAR(50);
    ip_address = db.Column(db.String(50))
    
    # Option 2: If you can't modify database, remove the ip_address field above
    # and use target_ip if that's what your database has:
    # target_ip = db.Column('target_ip', db.String(50))  # Use actual column name
    
    proxy_id = db.Column(db.Integer, db.ForeignKey('proxies.id'), nullable=True)
    proxy = db.relationship('Proxies', backref=db.backref('scans', lazy=True))

    def __repr__(self):
        return f'<Scan {self.id} - {self.scan_type}>'
