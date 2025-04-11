# models.py
from app import db

class Host(db.Model):
    __tablename__ = 'hosts'

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    resolved_hostname = db.Column(db.String(100), nullable=True)
    open_ports = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Host {self.ip}>"

class Scan(db.Model):
    __tablename__ = 'scans'

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='in-progress')
    date = db.Column(db.DateTime, nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id'))
    host = db.relationship('Host', backref='scans')

    def __repr__(self):
        return f"<Scan {self.id} for {self.host.ip}>"
