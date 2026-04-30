from conf.app_factory import create_app
from conf.logging_config import configure_logging
from routes.admin_routes import admin_bp
from routes.public_routes import public_bp
from routes.quant_routes import quant_bp
from service.bootstrap_service import bootstrap_runtime


app = create_app()
configure_logging(app)
app.register_blueprint(public_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(quant_bp)


bootstrap_runtime(app.logger)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=39997)
