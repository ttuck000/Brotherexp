from flask import Flask, render_template, session, redirect, request, url_for, jsonify
import sys
import os
import json
from werkzeug.middleware.proxy_fix import ProxyFix

# Determine base path that contains project-level `templates` and `static`.
# When running as a PyInstaller onefile exe, resources are unpacked into sys._MEIPASS.
if getattr(sys, "frozen", False):
    base_path = getattr(sys, "_MEIPASS")
else:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Make sure parent_dir points to project root (or _MEIPASS when frozen)
parent_dir = base_path

# Add parent_dir to sys.path to preserve existing behavior
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from config import Config
from app.utils.db import db
from flask_login import LoginManager

login_manager = LoginManager()  # module-level so other modules can import it

# Load language files
LANGUAGES = {}
language_dir = os.path.join(os.path.dirname(__file__), 'translations')  # app/translations
for lang_code in ['ko', 'en', 'th']:
    lang_file = os.path.join(language_dir, f'{lang_code}.json')
    if os.path.exists(lang_file):
        with open(lang_file, 'r', encoding='utf-8') as f:
            LANGUAGES[lang_code] = json.load(f)
    else:
        print(f"Warning: Language file not found: {lang_file}")
        LANGUAGES[lang_code] = {}

def create_app():
    # Use absolute template/static dirs so Flask finds them in both dev and bundled exe.
    template_dir = os.path.join(parent_dir, 'templates')
    static_dir = os.path.join(parent_dir, 'static')

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(Config)
    
    app.config.update({
        'SECRET_KEY': 'your-stable-secret-key',           # 여러 인스턴스면 동일하게
        'SESSION_COOKIE_SECURE': False,                   # HTTP 테스트용 (HTTPS면 True)
        'SESSION_COOKIE_SAMESITE': 'Lax',                 # 또는 'None' + Secure=True for cross-site
        'SESSION_COOKIE_DOMAIN': None                     # 도메인 고정 설정되어 있으면 제거/조정
    })

    db.init_app(app)

    # initialize flask-login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # register user loader
    from app.auth.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route('/change-language/<language>')
    def change_language(language):
        if language in ['ko', 'en', 'th']:
            session['language'] = language
        return redirect(request.referrer or url_for('home'))

    @app.before_request
    def ensure_language():
        # 세션에 언어가 없으면 기본으로 영어('en')를 설정
        if 'language' not in session:
            session['language'] = 'en'

    @app.context_processor
    def utility_processor():
        def get_text(key):
            try:
                # 기본 언어를 'en'으로 변경
                lang = session.get('language', 'en')
                return LANGUAGES.get(lang, {}).get(key, LANGUAGES.get('en', {}).get(key, key))
            except Exception:
                return key
        return dict(get_text=get_text)

    @app.route('/')
    def home():
        """대시보드: 회사(사업부) 카드 안에 계정코드별 PAYMENT, 맨 아래 전체 합계만 한 줄."""
        from datetime import date, timedelta
        from decimal import Decimal
        import pyodbc

        today = date.today()
        ym = (request.args.get('ym') or '').strip()
        if len(ym) >= 7 and ym[4:5] == '-':
            try:
                y = int(ym[0:4])
                mo = int(ym[5:7])
                if not (1 <= mo <= 12):
                    raise ValueError()
            except (ValueError, TypeError):
                y, mo = today.year, today.month
        else:
            y, mo = today.year, today.month

        start_d = date(y, mo, 1)
        if mo == 12:
            end_d = date(y + 1, 1, 1)
        else:
            end_d = date(y, mo + 1, 1)

        # title_key → static image under static/images/dashboard (logos); codes = COST_CENTER in DB
        buckets = [
            ('dashboard_div_clinic', ('Clinic', 'CLINIC', '클리닉', 'clinic')),
            ('dashboard_div_service', ('Service', 'SERV', 'SERVICE', '용역', 'service')),
            ('dashboard_div_uniform', ('Uniform', 'UNIFORM', '유니폼', 'uniform')),
            ('dashboard_div_tour', ('Tour', 'TOUR', '투어', 'tour')),
        ]
        dashboard_title_img = {
            'dashboard_div_clinic': 'images/dashboard/card_bbmedical.png',
            'dashboard_div_service': 'images/dashboard/card_vip.png',
            'dashboard_div_uniform': 'images/dashboard/card_uniform.png',
            'dashboard_div_tour': 'images/dashboard/card_bbthaitour.png',
        }

        def ph(codes):
            return ','.join('?' * len(codes))

        code_expr = (
            "COALESCE(NULLIF(LTRIM(RTRIM(CAST(a.Actual_Code AS NVARCHAR(100)))), ''), N'—')"
        )
        cc_expr = "LTRIM(RTRIM(CAST(a.COST_CENTER AS NVARCHAR(200))))"

        lang = session.get('language') or 'en'
        if lang == 'ko':
            account_name_col = 'ac.NAME_KO'
        elif lang == 'th':
            account_name_col = 'ac.NAME_TH'
        else:
            account_name_col = 'ac.NAME_EN'

        name_line = (
            f"COALESCE(NULLIF(LTRIM(RTRIM({account_name_col})), N''), "
            f"NULLIF({code_expr}, N'—'), N'—')"
        )

        cards_out = []
        conn_str = app.config.get('PYODBC_CONN_STR') or Config.PYODBC_CONN_STR

        try:
            conn = pyodbc.connect(conn_str)
            cur = conn.cursor()
            for title_key, codes in buckets:
                sql_rows = (
                    "SELECT sub.acct_code, MAX(sub.acct_name) AS acct_name, "
                    "SUM(sub.line_pay) AS pay_sum "
                    "FROM ( "
                    f"SELECT {code_expr} AS acct_code, "
                    f"{name_line} AS acct_name, "
                    "ISNULL(TRY_CAST(a.PAYMENT AS DECIMAL(18,2)), 0) AS line_pay "
                    "FROM dbo.Account_Actual a "
                    "LEFT JOIN dbo.code_Account ac "
                    "  ON a.Actual_Code = ac.account_code "
                    "  AND LTRIM(RTRIM(CAST(a.COST_CENTER AS NVARCHAR(200)))) = "
                    "     LTRIM(RTRIM(ISNULL(ac.company, N''))) "
                    f"WHERE a.BILLING_DATE IS NOT NULL AND a.BILLING_DATE >= ? AND a.BILLING_DATE < ? "
                    f"AND {cc_expr} IN ({ph(codes)}) "
                    ") sub "
                    "GROUP BY sub.acct_code "
                    "ORDER BY sub.acct_code"
                )
                cur.execute(sql_rows, (start_d, end_d, *codes))
                rows = []
                subtotal = Decimal('0')
                for r in cur.fetchall():
                    code_val = r[0]
                    name_val = (r[1] or '').strip() if r[1] is not None else ''
                    amt = Decimal(str(r[2] if r[2] is not None else 0))
                    subtotal += amt
                    display_name = name_val or (str(code_val).strip() if code_val is not None else '')
                    rows.append({
                        'code': code_val,
                        'name': display_name,
                        'amount': amt,
                    })
                cards_out.append({
                    'title_key': title_key,
                    'title_img': dashboard_title_img.get(title_key, ''),
                    'subtitle': '',
                    'rows': rows,
                    'amount': subtotal,
                })
            cur.close()
            conn.close()
        except Exception as e:
            app.logger.exception('home dashboard cost query failed: %s', e)
            cards_out = [
                {
                    'title_key': t,
                    'title_img': dashboard_title_img.get(t, ''),
                    'subtitle': '',
                    'rows': [],
                    'amount': Decimal('0'),
                }
                for t, _ in buckets
            ]

        total = sum((c['amount'] for c in cards_out), Decimal('0'))

        period_end = end_d - timedelta(days=1)
        period_label = f'{start_d.isoformat()} ~ {period_end.isoformat()}'

        ym_str = f'{y:04d}-{mo:02d}'
        return render_template(
            'index.html',
            dashboard_month=ym_str,
            dashboard_cards=cards_out,
            dashboard_total=total,
            dashboard_period_label=period_label,
        )
    
    # Blueprint registration (use consistent url_prefix for purchase)
    from app.auth import bp as auth_bp
    from app.inventory import bp as inventory_bp
    from app.purchase import bp as purchase_bp
    from app.sales import bp as sales_bp
    from app.base import bp as base
    from app.accounting import bp as acc_bp
    from app.financial import financial as financial_bp
    from app.dashboard.routes import dashboard as dashboard_bp
    from app.production import bp as production
    from app.other import bp as other_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    # Register purchase under /purchase so routes like /purchase/save work
    app.register_blueprint(purchase_bp, url_prefix='/purchase')
    app.register_blueprint(sales_bp)
    app.register_blueprint(base)
    app.register_blueprint(acc_bp, url_prefix='/accounting')
    app.register_blueprint(financial_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(production)
    app.register_blueprint(other_bp)

    # Register Jinja globals and filters
    app.jinja_env.globals.update(fmt_int=fmt_int, fmt_money=fmt_money, fmt_pct=fmt_pct)
    app.jinja_env.filters.update(fmt_int=fmt_int, fmt_money=fmt_money, fmt_pct=fmt_pct)

    for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
        print(r.rule, "->", r.endpoint)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    @login_manager.unauthorized_handler
    def _unauthorized_callback():
        # If request is AJAX, return 401 JSON instead of HTML redirect
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': 'unauthorized'}), 401
        return redirect(url_for('auth.login'))

    return app

# format helpers (unchanged)
def fmt_int(value):
    if value is None or value == '':
        return ''
    try:
        return f"{int(value):,}"
    except Exception:
        try:
            return f"{int(float(value)):,}"
        except Exception:
            return str(value)

def fmt_money(value):
    if value is None or value == '':
        return ''
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)

def fmt_pct(value):
    if value is None or value == '':
        return ''
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)

# Create the app instance used by run.py and PyInstaller bundle
app = create_app()

@app.route('/login')
def login_alias():
    return redirect(url_for('auth.login'))

import sys
try:
    # Python 3.7+: reconfigure stdout to UTF-8 so print() won't raise on Korean characters
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    # best-effort — environment may not support reconfigure
    pass