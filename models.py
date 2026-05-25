from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    """Application user for sign-in and audit tracking"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.email}>'

class Dealer(db.Model):
    """Model for dealer/client data"""
    __tablename__ = 'dealers'
    
    id = db.Column(db.String(10), primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    contact_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    citations = db.relationship('Citation', backref='dealer', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Dealer {self.id}: {self.name}>'
    
    def get_citation_count(self):
        """Get total citations built for this dealer"""
        return self.citations.count()
    
    def get_recent_citations(self, months=6):
        """Get citations built in the last N months"""
        cutoff_date = datetime.utcnow() - timedelta(days=30*months)
        return self.citations.filter(Citation.created_at >= cutoff_date).all()
    
    def get_available_citations(self, months=6):
        """Get list of citations NOT built in the last N months"""
        recent = self.get_recent_citations(months)
        recent_dir_ids = [c.directory_id for c in recent]
        
        available = BacklinkDirectory.query.filter(
            BacklinkDirectory.id.notin_(recent_dir_ids),
            BacklinkDirectory.active == True
        ).all()
        
        return available


class BacklinkDirectory(db.Model):
    """Model for backlink directories"""
    __tablename__ = 'backlink_directories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationships
    citations = db.relationship('Citation', backref='directory', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('User', foreign_keys=[created_by_id], lazy='joined')
    updated_by = db.relationship('User', foreign_keys=[updated_by_id], lazy='joined')
    
    def __repr__(self):
        return f'<BacklinkDirectory {self.id}: {self.name}>'


class Citation(db.Model):
    """Model for citation records (when and where a citation was built)"""
    __tablename__ = 'citations'
    
    id = db.Column(db.Integer, primary_key=True)
    dealer_id = db.Column(db.String(10), db.ForeignKey('dealers.id'), nullable=False)
    directory_id = db.Column(db.Integer, db.ForeignKey('backlink_directories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id], lazy='joined')
    updated_by = db.relationship('User', foreign_keys=[updated_by_id], lazy='joined')
    
    def __repr__(self):
        return f'<Citation {self.id}: {self.dealer_id} -> {self.directory.name}>'
    
    def is_recent(self, months=6):
        """Check if this citation is within the recency period"""
        cutoff_date = datetime.utcnow() - timedelta(days=30*months)
        return self.created_at >= cutoff_date


class ActivityLog(db.Model):
    """Recent activity feed for user actions across the app."""
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actor = db.relationship('User', foreign_keys=[actor_id], lazy='joined')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<ActivityLog {self.action} {self.entity_type}:{self.entity_id}>'


def init_db(app):
    """Initialize database with Flask app context"""
    with app.app_context():
        db.create_all()
        print("Database initialized successfully!")
