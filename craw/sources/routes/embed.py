"""
Router Embed - Trang và API embedding documents
"""
from flask import Blueprint, render_template, jsonify

from sources.services.embed_service import embed_documents, count_unembedded

embed_bp = Blueprint("embed", __name__, url_prefix="")


@embed_bp.route("/embed")
def embed_page():
    return render_template("embed.html")


@embed_bp.route("/api/embed/stats")
def api_embed_stats():
    unembedded = count_unembedded()
    return jsonify({"unembedded": unembedded})


@embed_bp.route("/api/embed/run", methods=["POST"])
def api_embed_run():
    try:
        result = embed_documents()
        return jsonify(result)
    except Exception as e:
        return jsonify({"embedded": 0, "total": 0, "error": str(e)}), 500
