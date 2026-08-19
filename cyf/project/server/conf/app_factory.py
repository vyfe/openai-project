from flask import Flask, jsonify, request
from flask_cors import CORS


def _probe_components() -> dict:
    """轻量级组件探针。被 /health 调用，确保每个依赖实际可达。"""
    components: dict = {}
    try:
        from quant.db import quant_db

        quant_db.execute_sql("SELECT 1").fetchone()
        components["quant_db"] = "ok"
    except Exception as exc:
        components["quant_db"] = f"error: {exc}"
    return components


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 52428800
    CORS(
        app,
        supports_credentials=True,
        origins=["*"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With", "User-Agent", "Cache-Control"],
        methods=["GET", "PUT", "POST", "DELETE", "OPTIONS"],
    )

    @app.after_request
    def after_request(response):
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Requested-With,User-Agent,Cache-Control")
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    @app.route("/", methods=["GET", "POST", "OPTIONS"])
    def handle_options():
        if request.method == "OPTIONS":
            return jsonify({"status": "OK"})
        return "", 200

    @app.route("/health", methods=["GET"])
    def health_check():
        components = _probe_components()
        overall = "ok" if all(value == "ok" for value in components.values()) else "degraded"
        code = 200 if overall == "ok" else 503
        return jsonify({
            "status": overall,
            "service": "openai-project",
            "components": components,
        }), code

    return app
