from flask import Blueprint

bp = Blueprint('sales', __name__, url_prefix='/sales')

from app.sales import routes
