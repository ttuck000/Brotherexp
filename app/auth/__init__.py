from flask import Blueprint

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Import routes so they register on `bp`; do NOT import a separate `auth` blueprint
from app.auth import routes  # routes should reference `bp` from this package
