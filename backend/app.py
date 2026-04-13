from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from routes.scrape_routes import scrape_bp
from models.db import migrate_db

app = Flask(__name__)

# 🔥 MANUAL CORS FIX (100% WORKING)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

@app.errorhandler(Exception)
def handle_app_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    return jsonify({'error': str(e)}), 500

@app.route("/")
def home():
    return "Lead Generation API is running!"

app.register_blueprint(scrape_bp)

if __name__ == "__main__":
    migrate_db()
    app.run(debug=True)