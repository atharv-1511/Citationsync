"""
Citation Building Management System
Main Flask Application
"""
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, g, get_flashed_messages
from flask_cors import CORS
from config import config
from models import db, User, Dealer, BacklinkDirectory, Citation, ActivityLog
from sqlalchemy import inspect, text, func
from werkzeug.exceptions import HTTPException
import os
from datetime import datetime, timedelta, timezone
import re
import json
import random
from collections import OrderedDict
from html import unescape
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def get_current_user():
    """Return the signed-in user for the current request."""
    if hasattr(g, 'current_user'):
        return g.current_user

    user_id = session.get('user_id')
    if not user_id:
        return None

    return db.session.get(User, user_id)


def to_utc_iso(value):
    """Serialize naive UTC datetimes as explicit UTC ISO 8601 strings."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def log_activity(action, entity_type, description, actor=None, entity_id=None):
    """Persist a recent activity item without interrupting the main action."""
    try:
        db.session.add(ActivityLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            description=description,
            actor_id=actor.id if actor else None,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def serialize_activity(activity):
    return {
        'id': activity.id,
        'action': activity.action,
        'entity_type': activity.entity_type,
        'entity_id': activity.entity_id,
        'description': activity.description,
        'actor': activity.actor.full_name if activity.actor else 'System',
        'created_at': to_utc_iso(activity.created_at),
    }


def _strip_html(value):
    if not value:
        return ''
    cleaned = re.sub(r'<[^>]+>', ' ', value)
    cleaned = unescape(cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _normalize_url(value):
    text_value = (value or '').strip()
    if not text_value:
        return None
    if not re.match(r'^https?://', text_value, flags=re.I):
        text_value = f'https://{text_value.lstrip("/")}'
    return text_value


def scrape_website_context(url, timeout=7):
    """Fetch lightweight SEO context from the dealer website homepage."""
    normalized = _normalize_url(url)
    if not normalized:
        return {
            'ok': False,
            'error': 'Missing website URL',
            'website_url': None,
        }

    try:
        request_obj = Request(
            normalized,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; CitationSyncBot/1.0; +https://example.com/bot)'
            },
        )
        with urlopen(request_obj, timeout=timeout) as response:
            final_url = response.geturl() or normalized
            raw_html = response.read(250000)

        html = raw_html.decode('utf-8', errors='ignore')
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.I | re.S)
        meta_desc_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            html,
            flags=re.I | re.S,
        )
        meta_keywords_match = re.search(
            r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\'](.*?)["\']',
            html,
            flags=re.I | re.S,
        )
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, flags=re.I | re.S)

        p_blocks = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.I | re.S)
        snippet_parts = [_strip_html(block) for block in p_blocks[:3]]
        snippet = ' '.join([part for part in snippet_parts if part]).strip()

        return {
            'ok': True,
            'website_url': final_url,
            'title': _strip_html(title_match.group(1))[:200] if title_match else '',
            'meta_description': _strip_html(meta_desc_match.group(1))[:300] if meta_desc_match else '',
            'meta_keywords': _strip_html(meta_keywords_match.group(1))[:300] if meta_keywords_match else '',
            'h1': _strip_html(h1_match.group(1))[:200] if h1_match else '',
            'snippet': snippet[:350],
        }
    except Exception as exc:
        return {
            'ok': False,
            'website_url': normalized,
            'error': str(exc),
        }


def _tokenize_text(value):
    return [
        token.strip()
        for token in re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).split()
        if token and len(token.strip()) > 2
    ]


def _trim_to_length(value, max_length=200):
    text_value = str(value or '').strip()
    if len(text_value) <= max_length:
        return text_value
    short = text_value[: max_length - 1].strip()
    pivot = short.rfind(' ')
    if pivot > 40:
        short = short[:pivot].strip()
    return f'{short}.'


def _word_count(value):
    return len([token for token in re.split(r'\s+', str(value or '').strip()) if token])


def _trim_to_word_range(value, min_words=50, max_words=80):
    text_value = re.sub(r'\s+', ' ', str(value or '').strip())
    words = text_value.split()
    if len(words) <= max_words:
        return text_value
    trimmed = ' '.join(words[:max_words]).strip()
    return trimmed.rstrip('.,;:!') + '.'


def _dedupe_keywords(keywords, min_count=15, max_count=25):
    ordered = []
    seen = set()
    stopwords = {
        'and', 'the', 'for', 'with', 'from', 'that', 'this', 'your', 'our', 'their',
        'home', 'page', 'website', 'site', 'dealer', 'dealership', 'auto', 'automotive',
    }
    for keyword in keywords:
        normalized = re.sub(r'\s+', ' ', str(keyword or '').strip().lower())
        if not normalized or normalized in seen or normalized in stopwords:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    if len(ordered) < min_count:
        return ordered
    return ordered[:max_count]


def _remove_dealer_name(text_value, dealer_name):
    result = str(text_value or '')
    if dealer_name:
        pattern = re.escape(str(dealer_name).strip())
        result = re.sub(pattern, '', result, flags=re.I)
    result = re.sub(r'\s{2,}', ' ', result)
    result = re.sub(r'\s+([,.;:!?])', r'\1', result).strip(' ,;:')
    return result


def build_local_seo_content(dealer_name, website_url, scraped_context=None, generation_index=1, regenerate=False):
    """Create SEO content from dealer name + dealer website context with varied phrasing."""
    clean_dealer_name = str(dealer_name or '').strip()
    clean_url = _normalize_url(website_url) or ''

    host = clean_url
    try:
        host = (urlparse(clean_url).hostname or clean_url).replace('www.', '')
    except Exception:
        host = clean_url.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

    host_label = (host.split('.')[0] if host else 'website') or 'website'
    scraped_context = scraped_context or {}

    page_title = scraped_context.get('title') or 'the dealership site'
    page_topic = scraped_context.get('h1') or 'vehicle sales and service'
    page_snippet = scraped_context.get('meta_description') or scraped_context.get('snippet') or 'dealership information and support'

    dealer_terms = _tokenize_text(clean_dealer_name)
    host_terms = _tokenize_text(host_label)
    context_terms = _tokenize_text(' '.join([
        scraped_context.get('title', ''),
        scraped_context.get('h1', ''),
        scraped_context.get('meta_description', ''),
        scraped_context.get('meta_keywords', ''),
        scraped_context.get('snippet', ''),
    ]))

    keyword_seed = [
        host_label,
        host,
        *dealer_terms[:6],
        *host_terms[:6],
        *context_terms[:10],
        'dealer',
        'automotive',
        'inventory',
        'service',
        'sales',
        'financing',
        'maintenance',
        'parts',
        'used cars',
        'new cars',
        'certified pre-owned',
        'schedule service',
        'auto repair',
        'truck',
        'suv',
        'sedan',
        'lease deals',
    ]
    keyword_set = _dedupe_keywords(keyword_seed, min_count=15, max_count=25)
    random.shuffle(keyword_set)

    opening_options = [
        'This dealership website presents a clear shopping experience for drivers comparing vehicles, services, and ownership support.',
        'Visitors can use the website to review inventory details, financing paths, and service resources in one convenient place.',
        'The site is designed to help shoppers evaluate vehicles, explore support options, and understand the dealership offering.',
        'Online visitors can quickly find information about available vehicles, finance opportunities, and maintenance support.',
    ]
    service_options = [
        f'The homepage and supporting pages highlight useful information about {page_topic.lower()} and the broader customer journey.',
        f'The website content suggests attention to inventory browsing, financing assistance, and service scheduling for customers.',
        f'Useful sections on {host} help visitors understand vehicle choices, support options, and the buying process.',
        f'The site provides a practical overview of services that matter to shoppers, including sales support and post-purchase care.',
    ]
    inventory_options = [
        'Relevant inventory details and shopping tools help users compare options before reaching out for the next step.',
        'The overall structure supports search visibility for vehicle listings, finance information, and service-related pages.',
        'Content on the site appears organized for customers seeking model information, service details, and dealership assistance.',
        'Clear page messaging helps prospective buyers and owners move through discovery, service, and follow-up actions.',
    ]
    closing_options = [
        f'The web presence feels built for practical dealership research, with emphasis on helpful, easy-to-navigate information from {host}.',
        f'Overall, the site supports customer decision-making with relevant dealership details and a useful online experience from {host}.',
        f'This online presence is suited to shoppers looking for vehicle options, finance support, and service information.',
        f'The website gives customers a simple path to explore offerings and move confidently toward the right dealership action.',
    ]

    description = _remove_dealer_name(
        ' '.join([
            random.choice(opening_options),
            random.choice(service_options),
            random.choice(inventory_options),
            random.choice(closing_options),
        ]),
        clean_dealer_name,
    )
    description = re.sub(r'\s+', ' ', description).strip()
    description = _trim_to_word_range(description, 50, 80)
    if _word_count(description) < 50:
        description = _trim_to_word_range(
            f'{description} The website supports vehicle shoppers with practical sales, financing, and service information while keeping the experience straightforward and informative.',
            50,
            80,
        )

    meta_description_options = [
        f'Explore inventory, financing, and service information on {host} for a focused dealership experience.',
        f'Visit {host} to review vehicle options, financing support, and service details in a clear online format.',
        f'Use {host} to compare vehicles, learn about support options, and discover dealership resources.',
        f'Find practical dealership information on {host} covering sales, financing, and service support.',
    ]
    meta_description = _remove_dealer_name(random.choice(meta_description_options), clean_dealer_name)
    meta_description = _trim_to_length(meta_description, 160)
    if len(meta_description) < 140:
        meta_description = _trim_to_length(
            f'{meta_description} Browse current inventory, financing details, and service information to support your next dealership visit.',
            160,
        )

    meta_keywords = ', '.join(keyword_set[:25])

    return {
        'description': description,
        'meta_description': meta_description,
        'meta_keywords': meta_keywords,
    }


def _extract_json_object(value):
    if not value:
        return None
    match = re.search(r'\{[\s\S]*\}', value)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def generate_ai_seo_content(dealer_name, website_url, scraped_context, regenerate=False):
    """Generate SEO content using OpenAI Chat Completions API when configured."""
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return None, 'OPENAI_API_KEY is not configured'

    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini').strip() or 'gpt-4o-mini'
    style_hint = 'Create a new angle and phrasing than previous attempts.' if regenerate else 'Create a strong first draft.'

    prompt = (
        'Draft a short description, META Keywords, and META Description. Keep the point in mind: Less proximity, no repetition of dealer name, no address. '
        'Include services, parts only if available. Read the link I provided and provide the content. Return JSON only with keys: description, meta_description, meta_keywords. '
        'Requirements: 1) Short Description must be 50-80 words. 2) Meta Description must be 140-160 characters. 3) Meta Keywords must contain 15-25 relevant keywords separated by commas. '
        'Guidelines: analyze the website before writing; focus on vehicle sales, financing, service, maintenance, and genuine parts only if available; do not include address; '
        'do not repeat the dealership name within the content; avoid location targeting or proximity phrases like near me, nearby, serving the area; keep it natural, unique, and SEO-friendly; '
        'do not keyword-stuff; keywords must be based on the actual services and inventory offered on the website. '
        'Dealer name and website are inputs for analysis only. '
        f'Name: {dealer_name}. Website: {website_url}. '
        f'Website title: {scraped_context.get("title", "")}. '
        f'Website h1: {scraped_context.get("h1", "")}. '
        f'Website meta description: {scraped_context.get("meta_description", "")}. '
        f'Website meta keywords: {scraped_context.get("meta_keywords", "")}. '
        f'Website snippet: {scraped_context.get("snippet", "")}. '
        f'{style_hint}'
    )

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are an SEO copywriter. Return strict JSON only.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 1.0,
        'response_format': {'type': 'json_object'},
    }

    try:
        body = json.dumps(payload).encode('utf-8')
        req = Request(
            'https://api.openai.com/v1/chat/completions',
            data=body,
            method='POST',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
        )
        with urlopen(req, timeout=20) as response:
            response_payload = json.loads(response.read().decode('utf-8', errors='ignore'))

        content = (
            response_payload.get('choices', [{}])[0]
            .get('message', {})
            .get('content', '')
        )
        parsed = _extract_json_object(content)
        if not parsed:
            return None, 'AI response did not contain valid JSON content'

        description = _trim_to_word_range(_remove_dealer_name(parsed.get('description', ''), dealer_name), 50, 80)
        meta_description = _trim_to_length(_remove_dealer_name(parsed.get('meta_description', ''), dealer_name), 160)
        meta_keywords = _dedupe_keywords(str(parsed.get('meta_keywords', '')).split(','), 15, 25)
        meta_keywords = ', '.join(meta_keywords)
        if not description or not meta_description or not meta_keywords:
            return None, 'AI response missing required fields'

        if _word_count(description) < 50:
            description = _trim_to_word_range(
                _remove_dealer_name(
                    f"{description} {scraped_context.get('snippet', '')} {scraped_context.get('h1', '')}",
                    dealer_name,
                ),
                50,
                80,
            )

        return {
            'description': description,
            'meta_description': meta_description,
            'meta_keywords': meta_keywords,
        }, None
    except Exception as exc:
        return None, str(exc)


def get_recent_dealers_page(page, per_page):
    pagination = Dealer.query.order_by(Dealer.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    dealer_ids = [dealer.id for dealer in pagination.items]
    cutoff_date = datetime.utcnow() - timedelta(days=30)

    citation_counts = {}
    recent_counts = {}
    if dealer_ids:
        citation_counts = {
            dealer_id: count
            for dealer_id, count in db.session.query(
                Citation.dealer_id,
                func.count(Citation.id)
            ).filter(Citation.dealer_id.in_(dealer_ids)).group_by(Citation.dealer_id).all()
        }
        recent_counts = {
            dealer_id: count
            for dealer_id, count in db.session.query(
                Citation.dealer_id,
                func.count(Citation.id)
            ).filter(
                Citation.dealer_id.in_(dealer_ids),
                Citation.created_at >= cutoff_date,
            ).group_by(Citation.dealer_id).all()
        }

    dealers = [{
        'id': dealer.id,
        'name': dealer.name,
        'citation_count': citation_counts.get(dealer.id, 0),
        'recent_months': recent_counts.get(dealer.id, 0)
    } for dealer in pagination.items]

    return pagination, dealers


def login_required(view):
    """Require a signed-in user for web and API requests."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
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
            full_name=app.config.get('EMPLOYEE_FULL_NAME') or '',
            role='employee',
            active=True,
        )
        # Use EMPLOYEE_PASSWORD if provided, otherwise fall back to DEFAULT_USER_PASSWORD
        emp_pass = app.config.get('EMPLOYEE_PASSWORD') or app.config.get('DEFAULT_USER_PASSWORD')
        employee.set_password(emp_pass)
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

    with app.app_context():
        try:
            ActivityLog.__table__.create(bind=db.engine, checkfirst=True)
        except Exception as exc:
            app.logger.warning('Activity log table initialization skipped: %s', exc)

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

        # Login page does not render flashed banners, so clear any stale flash
        # messages before the user signs in again.
        get_flashed_messages()

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
        log_activity('created', 'directory', f'{user.full_name if user else "System"} added directory {name}.', actor=user, entity_id=directory.id)

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
            log_activity('deleted', 'directory', f'{get_current_user().full_name} deleted directory {directory.name}.', actor=get_current_user(), entity_id=directory.id)
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
        log_activity('created', 'user', f'{get_current_user().full_name} created user {email}.', actor=get_current_user(), entity_id=user.id)

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
            BacklinkDirectory.query.filter_by(created_by_id=user.id).update({BacklinkDirectory.created_by_id: None})
            BacklinkDirectory.query.filter_by(updated_by_id=user.id).update({BacklinkDirectory.updated_by_id: None})
            Citation.query.filter_by(created_by_id=user.id).update({Citation.created_by_id: None})
            Citation.query.filter_by(updated_by_id=user.id).update({Citation.updated_by_id: None})
            db.session.delete(user)
            db.session.commit()
            log_activity('deleted', 'user', f'{get_current_user().full_name} deleted user {user.email}.', actor=get_current_user(), entity_id=user.id)
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
        log_activity('created', 'user', f'{get_current_user().full_name} created user {email}.', actor=get_current_user(), entity_id=user.id)

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
            BacklinkDirectory.query.filter_by(created_by_id=user.id).update({BacklinkDirectory.created_by_id: None})
            BacklinkDirectory.query.filter_by(updated_by_id=user.id).update({BacklinkDirectory.updated_by_id: None})
            Citation.query.filter_by(created_by_id=user.id).update({Citation.created_by_id: None})
            Citation.query.filter_by(updated_by_id=user.id).update({Citation.updated_by_id: None})
            db.session.delete(user)
            db.session.commit()
            log_activity('deleted', 'user', f'{get_current_user().full_name} deleted user {user.email}.', actor=get_current_user(), entity_id=user.id)
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
            return jsonify({'error': 'Dealer not found'}), 404
        
        # Get all citations for this dealer
        citations = Citation.query.filter_by(dealer_id=dealer_id).all()
        
        citation_data = [{
            'id': c.id,
            'directory_name': c.directory.name,
            'created_at': to_utc_iso(c.created_at),
            'notes': c.notes,
            'is_recent': c.is_recent(),
            'created_by': c.created_by.full_name if c.created_by else 'System',
        } for c in citations]
        
        return jsonify({
            'id': dealer.id,
            'name': dealer.name,
            'contact_info': dealer.contact_info,
            'total_citations': len(citations),
            'citations': citation_data,
            'created_at': to_utc_iso(dealer.created_at)
        })
    
    @app.route('/api/dealer/<dealer_id>/suggestions', methods=['GET'])
    @login_required
    def get_suggestions(dealer_id):
        """Get suggested citations for a dealer (respecting 6-month rule)"""
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        
        if not dealer:
            return jsonify({'error': 'Dealer not found'}), 404
        
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

    @app.route('/api/dealer/<dealer_id>/seo-context', methods=['GET'])
    @login_required
    def get_dealer_seo_context(dealer_id):
        """Return dealer website context for SEO generation (independent of citation directory)."""
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        if not dealer:
            return jsonify({'error': 'Dealer not found'}), 404

        requested_url = request.args.get('url', '').strip()
        website_url = requested_url or (dealer.contact_info or '').strip()
        normalized_url = _normalize_url(website_url)

        if not normalized_url:
            return jsonify({
                'ok': False,
                'dealer_id': dealer.id,
                'dealer_name': dealer.name,
                'website_url': None,
                'error': 'Dealer website URL is missing'
            }), 400

        scraped = scrape_website_context(normalized_url)
        return jsonify({
            'ok': scraped.get('ok', False),
            'dealer_id': dealer.id,
            'dealer_name': dealer.name,
            'website_url': scraped.get('website_url') or normalized_url,
            'scraped': scraped,
        }), 200

    @app.route('/api/dealer/<dealer_id>/seo-generate', methods=['POST'])
    @login_required
    def generate_dealer_seo_content(dealer_id):
        """Generate SEO content from dealer name + website context (optionally with ChatGPT API)."""
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        if not dealer:
            return jsonify({'error': 'Dealer not found'}), 404

        data = request.get_json() or {}
        requested_url = str(data.get('url', '') or '').strip()
        requested_mode = str(data.get('mode', 'auto') or 'auto').strip().lower()
        regenerate = bool(data.get('regenerate', False))
        generation_index = int(data.get('generation_count', 1) or 1)

        if requested_mode not in ('auto', 'ai', 'local'):
            requested_mode = 'auto'

        website_url = requested_url or (dealer.contact_info or '').strip()
        normalized_url = _normalize_url(website_url)
        if not normalized_url:
            return jsonify({'ok': False, 'error': 'Dealer website URL is missing'}), 400

        scraped = scrape_website_context(normalized_url)
        effective_context = scraped if scraped.get('ok') else {
            'title': '',
            'meta_description': '',
            'meta_keywords': '',
            'h1': '',
            'snippet': '',
        }

        local_generated = build_local_seo_content(
            dealer.name,
            normalized_url,
            effective_context,
            generation_index=generation_index,
            regenerate=regenerate,
        )

        used_mode = 'local'
        warning = None
        generated = local_generated

        if requested_mode in ('auto', 'ai'):
            ai_generated, ai_error = generate_ai_seo_content(
                dealer.name,
                normalized_url,
                effective_context,
                regenerate=regenerate,
            )
            if ai_generated:
                generated = ai_generated
                used_mode = 'ai'
            elif requested_mode == 'ai':
                warning = f'AI mode unavailable: {ai_error}. Falling back to local generation.'
            elif ai_error:
                warning = f'AI fallback not used: {ai_error}'

        return jsonify({
            'ok': True,
            'dealer_id': dealer.id,
            'dealer_name': dealer.name,
            'website_url': scraped.get('website_url') or normalized_url,
            'mode': used_mode,
            'warning': warning,
            'generated': generated,
            'scraped': scraped,
        }), 200
    
    @app.route('/api/citation/add', methods=['POST'])
    @login_required
    def add_citation():
        """Add a new citation record"""
        data = request.get_json()
        
        # Validate input
        if not data or 'dealer_id' not in data or 'directory_id' not in data:
            return jsonify({'error': 'Missing dealer_id or directory_id'}), 400
        
        dealer_id = data.get('dealer_id')
        directory_id = data.get('directory_id')
        
        # Verify dealer exists
        dealer = Dealer.query.filter_by(id=dealer_id).first()
        if not dealer:
            return jsonify({'error': 'Dealer not found'}), 404
        
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
            return jsonify({'error': 'Citation already exists for this dealer'}), 409
        
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
        log_activity(
            'created',
            'citation',
            f'{get_current_user().full_name} added citation {citation.directory.name} for dealer {dealer_id}' + (f' with notes: {citation.notes}' if citation.notes else '.'),
            actor=get_current_user(),
            entity_id=citation.id,
        )
        
        return jsonify({
            'success': True,
            'message': f'Citation added successfully',
            'citation': {
                'id': citation.id,
                'dealer_id': citation.dealer_id,
                'directory_name': citation.directory.name,
                'created_at': to_utc_iso(citation.created_at),
                'notes': citation.notes,
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
        
        # Get dealers needing citations this month in one grouped query instead of
        # querying each dealer individually.
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        recent_counts = {
            dealer_id: count
            for dealer_id, count in db.session.query(
                Citation.dealer_id,
                func.count(Citation.id)
            ).filter(Citation.created_at >= cutoff_date).group_by(Citation.dealer_id).all()
        }

        dealers_needing = []
        for dealer in Dealer.query.with_entities(Dealer.id, Dealer.name).all():
            recent_count = recent_counts.get(dealer.id, 0)
            if recent_count < 2:
                dealers_needing.append({
                    'id': dealer.id,
                    'name': dealer.name,
                    'citations_this_month': recent_count,
                    'needed': 2 - recent_count
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

        pagination, dealers = get_recent_dealers_page(page, per_page)

        return jsonify({
            'dealers': dealers,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })

    @app.route('/api/dashboard/summary', methods=['GET'])
    @login_required
    def dashboard_summary():
        """Fetch dashboard stats, dealers, and recent activity in one request."""
        page = request.args.get('page', 1, type=int)
        per_page = app.config['ITEMS_PER_PAGE']

        total_dealers = Dealer.query.count()
        total_directories = BacklinkDirectory.query.count()
        total_citations = Citation.query.count()
        avg_citations = total_citations / total_dealers if total_dealers > 0 else 0

        cutoff_date = datetime.utcnow() - timedelta(days=30)
        recent_counts = {
            dealer_id: count
            for dealer_id, count in db.session.query(
                Citation.dealer_id,
                func.count(Citation.id)
            ).filter(Citation.created_at >= cutoff_date).group_by(Citation.dealer_id).all()
        }

        dealers_needing = []
        for dealer_id, dealer_name in db.session.query(Dealer.id, Dealer.name).all():
            recent_count = recent_counts.get(dealer_id, 0)
            if recent_count < 2:
                dealers_needing.append({
                    'id': dealer_id,
                    'name': dealer_name,
                    'citations_this_month': recent_count,
                    'needed': 2 - recent_count,
                })

        pagination, dealers = get_recent_dealers_page(page, per_page)
        activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(7).all()

        # Include active and removed directories for dashboard
        active_dirs = BacklinkDirectory.query.filter_by(active=True).order_by(BacklinkDirectory.name).all()
        removed_dirs = BacklinkDirectory.query.filter_by(active=False).order_by(BacklinkDirectory.updated_at.desc()).all()

        def serialize_directory(d):
            return {
                'id': d.id,
                'name': d.name,
                'url': d.url,
                'citation_count': d.citations.count(),
                'created_by': d.created_by.full_name if d.created_by else 'System',
                'updated_at': to_utc_iso(d.updated_at)
            }

        return jsonify({
            'ok': True,
            'database': app.config['SQLALCHEMY_DATABASE_URI'],
            'database_env_present': bool(os.getenv('DATABASE_URL')),
            'database_env_is_supabase': bool(os.getenv('DATABASE_URL') and 'supabase.co' in os.getenv('DATABASE_URL')),
            'stats': {
                'total_dealers': total_dealers,
                'total_directories': total_directories,
                'total_citations': total_citations,
                'avg_citations_per_dealer': round(avg_citations, 2),
                'dealers_needing_citations': len(dealers_needing),
                'dealers_status': dealers_needing,
            },
            'dealers': dealers,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'recent_activities': [serialize_activity(activity) for activity in activities],
            'directories': {
                'active': [serialize_directory(d) for d in active_dirs],
                'removed': [serialize_directory(d) for d in removed_dirs],
            },
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


    @app.route('/api/activities', methods=['GET'])
    @login_required
    def get_activities():
        """Fetch activities within a date range. Defaults to last 10 days."""
        # Accept start and end as ISO dates (YYYY-MM-DD) or full ISO datetimes
        start = request.args.get('start')
        end = request.args.get('end')

        try:
            if start:
                start_dt = datetime.fromisoformat(start)
            else:
                start_dt = datetime.utcnow() - timedelta(days=10)

            if end:
                end_dt = datetime.fromisoformat(end)
            else:
                end_dt = datetime.utcnow()
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid date format. Use ISO format YYYY-MM-DD or full ISO datetime.'}), 400

        activities = ActivityLog.query.filter(
            ActivityLog.created_at >= start_dt,
            ActivityLog.created_at <= end_dt
        ).order_by(ActivityLog.created_at.desc()).all()

        return jsonify({
            'ok': True,
            'start': to_utc_iso(start_dt),
            'end': to_utc_iso(end_dt),
            'count': len(activities),
            'activities': [serialize_activity(a) for a in activities]
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
