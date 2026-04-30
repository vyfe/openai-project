from flask import Flask, jsonify, request
from flask_cors import CORS


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

    return app
