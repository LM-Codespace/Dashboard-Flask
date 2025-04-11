from app import create_app
from flask_sqlalchemy import SQLAlchemy

# Initialize db here, but not directly in the top level
app = create_app()
db = SQLAlchemy(app)

class Host(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(15), nullable=False)
    resolved_hostname = db.Column(db.String(100))
    open_ports = db.Column(db.String(100))
    location = db.Column(db.String(100))

    def __repr__(self):
        return f'<Host {self.name}>'

class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    status = db.Column(db.String(50))
    date = db.Column(db.DateTime)
    host_id = db.Column(db.Integer, db.ForeignKey('host.id'))
    host = db.relationship('Host', backref=db.backref('scans', lazy=True))

    def __repr__(self):
        return f'<Scan {self.id}>'
