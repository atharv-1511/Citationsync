import os
from datetime import datetime
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse
import socket


def _normalize_database_url(url):
    if not url:
        return None
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    if url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg2://', 1)

    parsed_url = urlparse(url)
    # Optionally prefer IPv4 addresses for environments without IPv6 egress.
    try_ipv4 = os.getenv('FORCE_IPV4', '').lower() in ('1', 'true', 'yes')
    if try_ipv4 and parsed_url.hostname:
        try:
            infos = socket.getaddrinfo(parsed_url.hostname, None, family=socket.AF_INET)
            if infos:
                # Use the first IPv4 address found
                ipv4 = infos[0][4][0]
                # Rebuild the netloc keeping credentials and port
                netloc = parsed_url.netloc
                if '@' in netloc:
                    creds, hostpart = netloc.rsplit('@', 1)
                    # hostpart may include :port
                    if ':' in hostpart:
                        _, port = hostpart.split(':', 1)
                        netloc = f"{creds}@{ipv4}:{port}"
                    else:
                        netloc = f"{creds}@{ipv4}"
                else:
                    # no credentials
                    if parsed_url.port:
                        netloc = f"{ipv4}:{parsed_url.port}"
                    else:
                        netloc = ipv4

                parsed_url = parsed_url._replace(netloc=netloc)
                url = urlunparse(parsed_url)
        except Exception:
            # If resolution fails, fall back to the original URL
            pass
    if parsed_url.hostname is None and '@' in url and '://' in url:
        scheme, remainder = url.split('://', 1)
        credentials, host_part = remainder.rsplit('@', 1)
        if ':' in credentials:
            username, password = credentials.split(':', 1)
            encoded_user = quote(username, safe='')
            encoded_password = quote(password, safe='')
            url = f'{scheme}://{encoded_user}:{encoded_password}@{host_part}'
            parsed_url = urlparse(url)

    if parsed_url.hostname and 'supabase.co' in parsed_url.hostname:
        query_params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
        query_params.setdefault('sslmode', 'require')
        parsed_url = parsed_url._replace(query=urlencode(query_params))
        return urlunparse(parsed_url)
    return url


def _default_database_url():
    database_url = _normalize_database_url(os.getenv('DATABASE_URL'))
    if database_url:
        return database_url

    if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        return 'sqlite:////tmp/backlinks.db'

    return 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database', 'backlinks.db')

class Config:
    """Base configuration"""
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = _default_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    
    # Application settings
    CITATIONS_PER_DEALER_MONTHLY = 2
    CITATION_RECENCY_MONTHS = 6
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'raskaratharv28@gmail.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Grayrock@04')
    ADMIN_FULL_NAME = os.getenv('ADMIN_FULL_NAME', 'Atharv Raskar')
    EMPLOYEE_EMAIL = os.getenv('EMPLOYEE_EMAIL', 'sakshi@example.com')
    EMPLOYEE_PASSWORD = os.getenv('EMPLOYEE_PASSWORD', 'ChangeMe123!')
    EMPLOYEE_FULL_NAME = os.getenv('EMPLOYEE_FULL_NAME', 'Sakshi')
    DEFAULT_USER_PASSWORD = os.getenv('DEFAULT_USER_PASSWORD', 'ChangeMe123!')
    
    # Pagination
    ITEMS_PER_PAGE = 20

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
