from flask import Flask, render_template, request, jsonify, redirect, send_file, flash, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
import pyodbc
from datetime import datetime, timedelta
import xlsxwriter
from io import BytesIO
import json
import os
import tempfile 
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl import Workbook
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
from config import config
from app.utils.db import db
from app.auth.models import User

import app.purchase.routes as purchase_routes
from app.inventory.routes import inventory_transaction_list_api
from app.inventory.routes import inventory_stock_list_api


import sys
import os

# determine base path (PyInstaller sets sys._MEIPASS when frozen)
if getattr(sys, "frozen", False):
    base_path = getattr(sys, "_MEIPASS")
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_path, "templates"),
    static_folder=os.path.join(base_path, "static")
)

# Create Flask with explicit template_folder path
app = Flask(__name__, template_folder=os.path.join(base_path, 'templates'))

# 로깅 설정
def setup_logger(app):
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')  

app = Flask(__name__)
app.config.from_object(config['development'])
app.config['PYODBC_CONN_STR'] = config['development'].PYODBC_CONN_STR
db.init_app(app)

# 간단한 다국어 로더/조회기 (없는 경우 키를 그대로 반환)
LANGUAGES = {}

def load_language():
    """
    가벼운 translations 폴더의 ko.json 등을 로드합니다.
    실제 프로젝트에서는 기존 구현으로 교체하세요.
    """
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(base_path, 'app', 'translations', 'ko.json'),
            os.path.join(base_path, 'translations', 'ko.json'),
            'app/translations/ko.json',
            'translations/ko.json'
        ]
        for p in possible_paths:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except Exception:
        app.logger.exception("load_language failed")
    return {}

# 전역 번역 데이터 초기화
LANGUAGES = load_language()

def get_text(key):
    """
    템플릿에서 사용: get_text('some_key')
    존재하지 않으면 key 자체를 반환하여 렌더링 에러 방지.
    """
    try:
        lang = session.get('language', 'ko')
        translations = LANGUAGES.get(lang, {})
        return translations.get(key, LANGUAGES.get('ko', {}).get(key, key))
    except Exception:
        app.logger.exception("get_text failed")
        return key

@app.context_processor
def utility_processor():
    # 템플릿 전역으로 get_text 사용 가능하게 함
    return dict(get_text=get_text)

# 로그인 매니저 초기화
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

# 로깅 설정
setup_logger(app)

@app.route('/change-language/<language>')
def change_language(language):
    # 허용 언어 검증 (필요시 확장)
    if language in ['ko', 'en', 'th']:
        session['language'] = language
    # 이전 페이지로 돌아감(낮으면 홈)
    return redirect(request.referrer or url_for('home'))

# Blueprint 등록 (프로젝트 원본대로 유지)
from app.auth.routes import auth
from app.base.routes import base
from app.inventory.routes import inventory
from app.purchase.routes import purchase
from app.sales.routes import sales
from app.financial.routes import financial
from app.dashboard.routes import dashboard, dashboard_purchase, dashboard_sales, dashboard_inventory, dashboard_financial, dashboard_sales_daily, dashboard_purchase_daily
from app.accounting import bp as acc

# 안전한 블루프린트 등록 예시
blueprints = [
    ('auth', auth),
    ('base', base),
    ('inventory', inventory),
    ('purchase', purchase),
    ('sales', sales),
    ('financial', financial),
    ('dashboard', dashboard),
    (acc.name if hasattr(acc, 'name') else 'accounting', acc)
]

for name, bp in blueprints:
    if name not in app.blueprints:
        try:
            app.register_blueprint(bp)
        except ValueError as e:
            app.logger.warning(f"Skipping blueprint {name}: {e}")

# 전역 API 라우트 등록 (수정)
app.add_url_rule('/api/purchases', view_func=purchase_routes.get_purchases)
app.add_url_rule('/api/vendors', view_func=purchase_routes.get_vendor_options)  # 혹은 get_vendors가 실제로 있으면 그걸 사용
app.add_url_rule('/api/purchase/<purchase_no>', view_func=purchase_routes.api_get_purchase)
app.add_url_rule('/api/warehouses', view_func=purchase_routes.api_get_warehouses)
app.add_url_rule('/api/items', view_func=purchase_routes.api_get_items)
app.add_url_rule('/api/vendor/options', view_func=purchase_routes.get_vendor_options)
app.add_url_rule('/api/warehouse/options', view_func=purchase_routes.get_warehouse_options)
app.add_url_rule('/api/currencies', view_func=purchase_routes.get_currencies)

# fallback so callers without blueprint prefix don't 404
app.add_url_rule('/api/inventory/stock_list', view_func=inventory_stock_list_api)
# similarly ensure transaction_list fallback exists (optional)
app.add_url_rule('/api/inventory/transaction_list', view_func=inventory_transaction_list_api)

# 에러 핸들러
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# 기타 유틸들(언어 로드 등)은 필요시 기존 코드 그대로 복원
@app.route('/')
def home():
    return render_template('index.html')

def fmt_money(value):
    """숫자(금액)를 '#,###.00' 형태로 포맷하거나 유효하지 않으면 '-' 반환"""
    try:
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return '-'
        v = float(value)
        return f"{v:,.2f}"
    except Exception:
        return '-'


def fmt_pct(value):
    """백분율/비율 표시: 소수 2자리. 유효하지 않으면 '-' 반환"""
    try:
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return '-'
        v = float(value)
        return f"{v:.2f}"
    except Exception:
        return '-'


def fmt_int(value):
    """정수(예: ID)를 천단위로 포맷, 유효하지 않으면 빈 문자열 반환"""
    try:
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return ''
        v = int(value)
        return f"{v:,}"
    except Exception:
        return ''

@app.context_processor
def utility_processor():
    # 템플릿 전역으로 유틸 함수들 노출
    return dict(
        get_text=get_text,
        fmt_money=fmt_money,
        fmt_pct=fmt_pct,
        fmt_int=fmt_int
    )

def create_app():
    app = Flask(__name__)
    # config, db.init_app(app), etc.

    # import and register blueprints here to avoid import-time side effects
    from app.auth.routes import auth
    from app.base.routes import base
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(base)

    return app          

if __name__ == "__main__":
    import webbrowser
    url = "http://127.0.0.1:7777"

    # Prevent opening multiple windows when the reloader runs
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            webbrowser.open_new(url)
        except Exception:
            pass

    # Run on 127.0.0.1 for local access. Change host='0.0.0.0' to allow external access
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=7777)
