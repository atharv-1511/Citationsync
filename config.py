import os
from datetime import datetime


def _normalize_database_url(url):
    if not url:
        return None
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    return url

class Config:
    """Base configuration"""
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.getenv('DATABASE_URL')
    ) or 'sqlite:///' + os.path.join(BASEDIR, 'database', 'backlinks.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    
    # Application settings
    CITATIONS_PER_DEALER_MONTHLY = 2
    CITATION_RECENCY_MONTHS = 6
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'raskaratharv28@gmail.com')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Grayrock@04')
    ADMIN_FULL_NAME = os.getenv('ADMIN_FULL_NAME', 'Atharv Raskar')
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
