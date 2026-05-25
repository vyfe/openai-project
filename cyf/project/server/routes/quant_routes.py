from flask import Blueprint

from routes.quant.client_routes import bp as quant_client_bp
from routes.quant.data_routes import bp as quant_data_bp
from routes.quant.scheduler_routes import bp as quant_scheduler_bp


quant_bp = Blueprint("quant_routes", __name__, url_prefix="/never_guess_my_usage/quant")

