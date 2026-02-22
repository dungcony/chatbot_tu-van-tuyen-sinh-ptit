# routers/__init__.py
from flask import Flask

from routers.chat import bp as chat_bp


def register_routers(app: Flask):
    """Đăng ký tất cả Blueprint vào app."""
    app.register_blueprint(chat_bp)
