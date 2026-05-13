from flask import Blueprint

bp = Blueprint('production', __name__)

from app.production import routes