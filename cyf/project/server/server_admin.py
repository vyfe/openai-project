from conf.app_factory import create_app
from routes.admin_routes import admin_bp


app = create_app()
app.register_blueprint(admin_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=39998, debug=True)
