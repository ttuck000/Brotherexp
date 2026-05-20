import os
from datetime import timedelta

class Config:
    # 기본 설정
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
    # 기본 데이터베이스 연결 문자열
    SQLALCHEMY_DATABASE_URI = (
        "mssql+pyodbc:///?odbc_connect=" +
        "DRIVER={ODBC Driver 17 for SQL Server};" +
        "SERVER=118.67.132.208,1433;" +
        "DATABASE=BRO_EXPENSE;" +
        "UID=brother;" +
        "PWD=jobgate@m1n;" +
        "TrustServerCertificate=yes;" +
        "Connection Timeout=30;" +
        "Command Timeout=30"
    )
    
    # 대체 연결 문자열 (문제가 있을 경우 사용)
    SQLALCHEMY_DATABASE_URI_ALTERNATIVE = (
        "mssql+pyodbc:///?odbc_connect=" +
        "DRIVER={SQL Server Native Client 11.0};" +
        "SERVER=118.67.132.208,1433;" +
        "DATABASE=BRO_EXPENSE;" +
        "UID=brother;" +
        "PWD=jobgate@m1n;" +
        "TrustServerCertificate=yes;" +
        "Connection Timeout=30;" +
        "Command Timeout=30"
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'max_overflow': 20
    }
    
    # 세션 설정
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    
    # 보안 설정
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or 'csrf-secret-key'
    
    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    
    # 로깅 설정
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'app.log'

    # ODBC connection string
    PYODBC_CONN_STR = (
        "DRIVER={ODBC Driver 17 for SQL Server};" +
        "SERVER=118.67.132.208,1433;" +
        "DATABASE=BRO_EXPENSE;" +
        "UID=brother;" +
        "PWD=jobgate@m1n;" +
        "TrustServerCertificate=yes;" +
        "Connection Timeout=30;" +
        "Command Timeout=30"
    )

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}