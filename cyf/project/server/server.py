from conf.app_factory import create_app
from conf.logging_config import configure_logging
from routes.admin_routes import admin_bp
from routes.public_routes import public_bp
from routes.quant.im_memory_routes import bp as quant_im_memory_bp
from routes.quant.strategy_routes import bp as quant_strategy_bp
from routes.quant.trade_routes import bp as quant_trade_bp
from routes.quant_routes import quant_bp
from routes.quant.client_routes import bp as quant_client_bp
from routes.quant.data_routes import bp as quant_data_bp
from routes.quant.scheduler_routes import bp as quant_scheduler_bp
from service.bootstrap_service import bootstrap_runtime


app = create_app()
configure_logging(app)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(quant_bp)
app.register_blueprint(quant_strategy_bp)
app.register_blueprint(quant_im_memory_bp)
app.register_blueprint(quant_trade_bp)
app.register_blueprint(quant_data_bp)
app.register_blueprint(quant_scheduler_bp)
app.register_blueprint(quant_client_bp)


bootstrap_runtime(app.logger)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=39997)
