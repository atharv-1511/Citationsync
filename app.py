"""
Citation Building Management System
Main Flask Application
"""
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, g
from flask_cors import CORS
from config import config
from models import db, User, Dealer, BacklinkDirectory, Citation
from sqlalchemy import inspect, text
from werkzeug.exceptions import HTTPException
import os
from datetime import datetime, timedelta


def get_current_user():
    """Return the signed-in user for the current request."""
    if hasattr(g, 'current_user'):
        return g.current_user

    user_id = session.get('user_id')
    if not user_id:
        return None

    return db.session.get(User, user_id)


def login_required(view):
    """Require a signed-in user for web and API requests."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please sign in to continue.', 'error')
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Require the admin role for privileged actions."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_admin:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Admin access required'}), 403
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return view(*args, **kwargs)

    return wrapped


def seed_default_users(app):
    """Create the default admin and employee accounts if they do not exist yet."""
    admin_email = app.config['ADMIN_EMAIL'].strip().lower()
    if admin_email and not User.query.filter_by(email=admin_email).first():
        admin = User(
            email=admin_email,
            full_name=app.config['ADMIN_FULL_NAME'],
            role='admin',
            active=True,
        )
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)

    employee_email = app.config.get('EMPLOYEE_EMAIL', '').strip().lower()
    if employee_email and not User.query.filter_by(email=employee_email).first():
        employee = User(
            email=employee_email,
            full_name=app.config.get('EMPLOYEE_FULL_NAME', 'Sakshi'),
            role='employee',
            active=True,
        )
        employee.set_password(app.config.get('EMPLOYEE_PASSWORD', app.config.get('DEFAULT_USER_PASSWORD')))
        db.session.add(employee)

    if admin_email or employee_email:
        db.session.commit()


def ensure_sqlite_schema(app):
    """Add missing columns to an existing SQLite database used by the prototype."""
    database_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if not database_uri.startswith('sqlite:///') or ':memory:' in database_uri:
        return

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    alterations = {
        'backlink_directories': ['updated_at', 'created_by_id', 'updated_by_id'],
        'citations': ['updated_at', 'created_by_id', 'updated_by_id'],
    }

    with db.engine.begin() as connection:
        for table_name, required_columns in alterations.items():
            if table_name not in existing_tables:
                continue

            current_columns = {column['name'] for column in inspector.get_columns(table_name)}
            for column_name in required_columns:
                if column_name not in current_columns:
                    if column_name.endswith('_id'):
                        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} INTEGER'))
                    else:
                        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} DATETIME'))

def create_app(config_name='development'):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)

    database_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if database_uri.startswith('sqlite:///') and ':memory:' not in database_uri:
        db_path = os.path.dirname(database_uri.replace('sqlite:///', ''))
        os.makedirs(db_path, exist_ok=True)

    @app.before_request
    def load_current_user():
        g.current_user = get_current_user()

    @app.context_processor
    def inject_user_context():
        current_user = get_current_user()
        return {
            'current_user': current_user,
            'is_admin_user': bool(current_user and current_user.is_admin),
            'config': app.config
        }

    serverless_runtime = bool(os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'))

    if not serverless_runtime:
        with app.app_context():
            try:
                db.create_all()
                seed_default_users(app)
                ensure_sqlite_schema(app)
            except Exception as exc:
                app.logger.warning('Database initialization skipped: %s', exc)
    else:
        app.logger.info('Skipping database bootstrap in serverless runtime.')
    
    # Register blueprints and routes
    register_routes(app)
    
    return app

def register_routes(app):
    """Register all routes"""
    
    @app.route('/')
    @login_required
    def index():
        """Home page"""
        return render_template('index.html')
    
    @app.route('/dealer')
    @login_required
    def dealer_page():
        """Dealer lookup page"""
        return render_template('dealer_lookup.html')
    
    @app.route('/add-citation')
    @login_required
    def add_citation_page():
        """Add citation page"""
        return render_template('add_citation.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard_page():
        """Dashboard page"""
        return render_template('dashboard.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Sign in with an organization email and password."""
        if get_current_user():
            return redirect(url_for('index'))

        error = None

        if request.method == 'POST':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')

            user = User.query.filter_by(email=email).first()
            if user and user.active and user.check_password(password):
                session['user_id'] = user.id
                flash(f'Welcome, {user.full_name}.', 'success')
                next_page = request.args.get('next') or url_for('index')
                return redirect(next_page)

            error = 'Invalid email or password.'

        return render_template('login.html', error=error)

    @app.route('/logout')
    def logout():
        """Sign out the current user."""
        session.pop('user_id', None)
        flash('You have been signed out.', 'success')
        return redirect(url_for('login'))

    @app.route('/admin')
    @login_required
    @admin_required
    def admin_page():
        """Admin console for adding directories."""
        directories = BacklinkDirectory.query.order_by(BacklinkDirectory.created_at.desc()).all()
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template('admin.html', directories=directories, users=users)

    @app.route('/admin/directories', methods=['POST'])
    @login_required
    @admin_required
    def create_directory():
        """Create a new backlink directory and make it available immediately."""
        name = request.form.get('name', '').strip()
        url_value = request.form.get('url', '').strip()

        if not name or not url_value:
            flash('Directory name and URL are required.', 'error')
            return redirect(url_for('admin_page'))

        if BacklinkDirectory.query.filter_by(name=name).first():
            flash('A directory with that name already exists.', 'error')
            return redirect(url_for('admin_page'))

        user = get_current_user()
        directory = BacklinkDirectory(
            name=name,
            url=url_value,
            active=True,
            created_by_id=user.id if user else None,
            updated_by_id=user.id if user else None,
        )
        db.session.add(directory)
        db.session.commit()

        flash(f'Added directory {name}.', 'success')
        return redirect(url_for('admin_page'))

    @app.route('/admin/directory/<int:dir_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_directory(dir_id):
        directory = BacklinkDirectory.query.get_or_404(dir_id)
        try:
            db.session.delete(directory)
            db.session.commit()
            flash(f'Deleted directory {directory.name}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Cannot delete directory {directory.name}, it is likely in use.', 'error')
        return redirect(url_for('admin_page'))

    @app.route('/admin/users', methods=['POST'])
    @login_required
    @admin_required
    def create_user():
        """Create a new user (admin can add employees)."""
        email = request.form.get('email', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password or not full_name:
            flash('Email, full name and password are required to create a user.', 'error')
            return redirect(url_for('admin_page'))

        # Prevent creating additional admins — only configured ADMIN_EMAIL is allowed admin role
        configured_admin = app.config.get('ADMIN_EMAIL', '').strip().lower()
        role = 'employee'
        if email == configured_admin:
            role = 'admin'

        if User.query.filter_by(email=email).first():
            flash('A user with that email already exists.', 'error')
            return redirect(url_for('admin_page'))

        user = User(email=email, full_name=full_name, role=role, active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'User {email} created.', 'success')
        return redirect(url_for('admin_page'))

    @app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
    @login_required
    @admin_required
    def delete_user(user_id):
        """Delete an existing user (admin only). Prevent deleting configured admin."""
        user = User.query.get_or_404(user_id)
        configured_admin = app.config.get('ADMIN_EMAIL', '').strip().lower()
        if user.email and user.email.lower() == configured_admin:
            flash('Cannot delete the configured admin user.', 'error')
            return redirect(url_for('admin_page'))

        try:
            db.session.delete(user)
            db.session.commit()
            flash(f'User {user.email} deleted.', 'success')
        except Exception:
            db.session.rollback()
            flash('Unable to delete user; user may be referenced elsewhere.', 'error')

        return redirect(url_for('admin_page'))

    # JSON API endpoints for AJAX-powered admin UI
    @app.route('/api/admin/users', methods=['POST'])
    @login_required
    @admin_required
    def api_create_user():
        data = request.get_json() or {}
        email = (data.get('email') or request.form.get('email') or '').strip().lower()
        full_name = (data.get('full_name') or request.form.get('full_name') or '').strip()
        password = (data.get('password') or request.form.get('password') or '').strip()

        if not email or not password or not full_name:
            return jsonify({'success': False, 'error': 'Email, full name and password are required.'}), 400

        configured_admin = app.config.get('ADMIN_EMAIL', '').strip().lower()
        role = 'employee'
        if email == configured_admin:
            role = 'admin'

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'User already exists.'}), 409

        user = User(email=email, full_name=full_name, role=role, active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({'success': True, 'user': {'id': user.id, 'email': user.email, 'full_name': user.full_name, 'role': user.role, 'created_at': user.created_at.isoformat()}}), 201

    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    @login_required
    @admin_required
    def api_delete_user(user_id):
        user = User.query.get_or_404(user_id)
        configured_admin = app.config.get('ADMIN_EMAIL', '').strip().lower()
        if user.email and user.email.lower() == configured_admin:
            return jsonify({'success': False, 'error': 'Cannot delete configured admin.'}), 403

        try:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'success': True}), 200
        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Unable to delete user.'}), 500
    
    # ===================== API ENDPOINTS =====================
    
    @app.route('/api/dealer/<dealer_id>', methods=['GET'])
    @login_required
    def get_dealer(dealer_id):
        """Get dealer information and citation history"""
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        
        if not dealer:
            return jsonify({'error': 'Cafe not found'}), 404
        
        # Get all citations for this dealer
        citations = Citation.query.filter_by(dealer_id=dealer_id).all()
        
        citation_data = [{
            'id': c.id,
            'directory_name': c.directory.name,
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_recent': c.is_recent(),
            'created_by': c.created_by.full_name if c.created_by else 'System',
        } for c in citations]
        
        return jsonify({
            'id': dealer.id,
            'name': dealer.name,
            'contact_info': dealer.contact_info,
            'total_citations': len(citations),
            'citations': citation_data,
            'created_at': dealer.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    @app.route('/api/dealer/<dealer_id>/suggestions', methods=['GET'])
    @login_required
    def get_suggestions(dealer_id):
        """Get suggested citations for a cafe (respecting 6-month rule)"""
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        
        if not dealer:
            return jsonify({'error': 'Cafe not found'}), 404
        
        # Get available citations
        available = dealer.get_available_citations(months=6)
        
        if len(available) == 0:
            return jsonify({
                'dealer_id': dealer_id,
                'suggestions': [],
                'message': 'No available citations at this time. All directories have been used in the last 6 months.'
            })
        
        suggestions = [{
            'id': s.id,
            'name': s.name,
            'url': s.url
        } for s in available]
        
        return jsonify({
            'dealer_id': dealer_id,
            'suggestions': suggestions,
            'available_count': len(available)
        })
    
    @app.route('/api/citation/add', methods=['POST'])
    @login_required
    def add_citation():
        """Add a new citation record"""
        data = request.get_json()
        
        # Validate input
        if not data or 'dealer_id' not in data or 'directory_id' not in data:
            return jsonify({'error': 'Missing cafe_id or directory_id'}), 400
        
        dealer_id = data.get('dealer_id')
        directory_id = data.get('directory_id')
        
        # Verify dealer exists
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        if not dealer:
            return jsonify({'error': 'Cafe not found'}), 404
        
        # Verify directory exists
        directory = BacklinkDirectory.query.filter_by(id=directory_id).first()
        if not directory:
            return jsonify({'error': 'Directory not found'}), 404
        
        # Check if citation already exists
        existing = Citation.query.filter_by(
            dealer_id=dealer_id,
            directory_id=directory_id
        ).first()
        
        if existing:
            return jsonify({'error': 'Citation already exists for this cafe'}), 409
        
        # Create new citation
        citation = Citation(
            dealer_id=dealer_id,
            directory_id=directory_id,
            notes=data.get('notes', ''),
            created_by_id=get_current_user().id,
            updated_by_id=get_current_user().id,
        )
        
        db.session.add(citation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Citation added successfully',
            'citation': {
                'id': citation.id,
                'dealer_id': citation.dealer_id,
                'directory_name': citation.directory.name,
                'created_at': citation.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'created_by': citation.created_by.full_name if citation.created_by else 'System'
            }
        }), 201
    
    @app.route('/api/citations/stats', methods=['GET'])
    @login_required
    def get_stats():
        """Get overall statistics"""
        total_dealers = Dealer.query.count()
        total_directories = BacklinkDirectory.query.count()
        total_citations = Citation.query.count()
        
        # Calculate average citations per dealer
        avg_citations = total_citations / total_dealers if total_dealers > 0 else 0
        
        # Get dealers needing citations this month
        dealers_needing = []
        for dealer in Dealer.query.all():
            recent = dealer.get_recent_citations(months=1)
            if len(recent) < 2:  # Need 2 per month
                dealers_needing.append({
                    'id': dealer.id,
                    'name': dealer.name,
                    'citations_this_month': len(recent),
                    'needed': 2 - len(recent)
                })
        
        return jsonify({
            'total_dealers': total_dealers,
            'total_directories': total_directories,
            'total_citations': total_citations,
            'avg_citations_per_dealer': round(avg_citations, 2),
            'dealers_needing_citations': len(dealers_needing),
            'dealers_status': dealers_needing
        })

    @app.route('/api/db-status', methods=['GET'])
    def db_status():
        """Public health check for database connectivity."""
        configured_uri = app.config['SQLALCHEMY_DATABASE_URI']
        env_database_url = os.getenv('DATABASE_URL')
        try:
            result = db.session.execute(text('SELECT 1')).scalar()
            return jsonify({
                'ok': True,
                'database': configured_uri,
                'database_env_present': bool(env_database_url),
                'database_env_is_supabase': bool(env_database_url and 'supabase.co' in env_database_url),
                'runtime': {
                    'flask_env': os.getenv('FLASK_ENV', 'production'),
                    'vercel': bool(os.getenv('VERCEL')),
                },
                'result': int(result) if result is not None else None,
            })
        except Exception as exc:
            app.logger.warning('Database status check failed: %s', exc)
            return jsonify({
                'ok': False,
                'database': configured_uri,
                'database_env_present': bool(env_database_url),
                'database_env_is_supabase': bool(env_database_url and 'supabase.co' in env_database_url),
                'runtime': {
                    'flask_env': os.getenv('FLASK_ENV', 'production'),
                    'vercel': bool(os.getenv('VERCEL')),
                },
                'error': str(exc),
            }), 503
    
    @app.route('/api/dealers', methods=['GET'])
    @login_required
    def get_all_dealers():
        """Get list of all dealers"""
        page = request.args.get('page', 1, type=int)
        per_page = app.config['ITEMS_PER_PAGE']
        
        pagination = Dealer.query.paginate(page=page, per_page=per_page)
        
        dealers = [{
            'id': d.id,
            'name': d.name,
            'citation_count': d.get_citation_count(),
            'recent_months': len(d.get_recent_citations(months=1))
        } for d in pagination.items]
        
        return jsonify({
            'dealers': dealers,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })
    
    @app.route('/api/directories', methods=['GET'])
    @login_required
    def get_directories():
        """Get list of all directories"""
        directories = BacklinkDirectory.query.filter_by(active=True).all()
        
        return jsonify({
            'directories': [{
                'id': d.id,
                'name': d.name,
                'url': d.url,
                'citation_count': d.citations.count(),
                'created_by': d.created_by.full_name if d.created_by else 'System'
            } for d in directories]
        })
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(Exception)
    def server_error(error):
        """Handle unexpected errors with route-aware API details."""
        if isinstance(error, HTTPException):
            return error

        app.logger.exception('Unhandled exception on %s %s', request.method, request.path)

        if request.path.startswith('/api/'):
            payload = {
                'error': 'Internal server error',
                'path': request.path,
                'method': request.method,
                'type': error.__class__.__name__,
            }
            if os.getenv('VERCEL') or os.getenv('FLASK_ENV', 'production') != 'production':
                payload['detail'] = str(error)
            return jsonify(payload), 500

        return jsonify({'error': 'Internal server error'}), 500

# Expose a top-level WSGI `app` for hosting platforms (Vercel, Gunicorn, etc.).
# This makes `from app import app` work and satisfies Vercel's requirement.
# Use the `FLASK_ENV` environment variable to control the config (defaults to 'production').
app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == '__main__':
    # When run locally, enable debug with the development config by default.
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5000)
