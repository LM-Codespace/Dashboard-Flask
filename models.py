from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy object in models (we'll initialize it later in app.py)
db = SQLAlchemy()

class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(100), nullable=False)  # Changed from 'ip' to 'ip_address'
    resolved_hostname = db.Column(db.String(100), nullable=True)
    open_ports = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Host {self.name}>'

class Proxies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100), nullable=False)  # 'ip' changed to 'ip_address'
    port = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'<Proxy {self.ip_address}:{self.port}>'

class Scan(db.Model):
    __tablename__ = 'scan'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    scan_type = db.Column(db.String(50))
    host_id = db.Column(db.Integer, db.ForeignKey('host.id'))
    host = db.relationship('Host', backref=db.backref('scans', lazy=True))

    def __repr__(self):
        return f'<Scan {self.id}>'
