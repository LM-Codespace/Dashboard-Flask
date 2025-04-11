# models.py
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(100), nullable=False)
    resolved_hostname = db.Column(db.String(100), nullable=True)
    open_ports = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Host {self.name}>'

class Proxies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'active' or 'inactive'
    type = db.Column(db.String(50), nullable=False)  # 'SOCKS5', 'HTTP', etc.

    def __repr__(self):
        return f'<Proxy {self.ip}:{self.port}>'

class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('host.id'), nullable=False)
    host = db.relationship('Host', backref=db.backref('scans', lazy=True))

    def __repr__(self):
        return f'<Scan {self.id} for {self.host.name}>'
