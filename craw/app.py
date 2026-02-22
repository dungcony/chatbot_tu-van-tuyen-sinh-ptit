#!/usr/bin/env python3
"""
Flask app - Admin TVTS Chatbot
Chạy: python app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from flask import Flask

from sources.routes.admin import admin_bp
from sources.routes.embed import embed_bp
from sources.routes.crawl import crawl_bp
from sources.routes.normalize import normalize_bp
from sources.routes.prepare import prepare_bp

app = Flask(
    __name__,
    template_folder="sources/pages",
    static_folder="sources/pages",
    static_url_path="/pages",
)

app.register_blueprint(admin_bp)
app.register_blueprint(embed_bp)
app.register_blueprint(crawl_bp)
app.register_blueprint(normalize_bp)
app.register_blueprint(prepare_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
