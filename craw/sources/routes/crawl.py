"""
Router Crawl - Trang và API crawl dữ liệu
"""
import os
import subprocess
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = ROOT / "sources" / "scripts"
LINKS_DIR = ROOT / "public" / "links"

crawl_bp = Blueprint("crawl", __name__, url_prefix="")


def _run_script(script_name: str, args: list[str]) -> tuple[int, str]:
    """Chạy script Python, trả về (exit_code, output)."""
    cmd = ["python", str(SCRIPTS_DIR / script_name)] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=1200,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out
    except subprocess.TimeoutExpired:
        return -1, "Timeout (quá 20 phút)"
    except Exception as e:
        return -1, str(e)


@crawl_bp.route("/crawl")
def crawl_page():
    json_files = []
    if LINKS_DIR.exists():
        json_files = [f.name for f in LINKS_DIR.glob("*.json")]
    return render_template("crawl.html", json_files=json_files)


@crawl_bp.route("/api/crawl/json", methods=["POST"])
def api_crawl_json():
    data = request.get_json() or {}
    file_name = data.get("file") or ""
    max_pages = data.get("max", 500)
    if not file_name:
        return jsonify({"ok": False, "error": "Chọn file JSON"}), 400
    if not (LINKS_DIR / file_name).exists():
        return jsonify({"ok": False, "error": "File không tồn tại"}), 400
    code, out = _run_script(
        "run_crawl_from_links.py",
        ["--mode", "json", "--file", file_name, "--max", str(max_pages)],
    )
    return jsonify({
        "ok": code == 0,
        "output": out,
        "error": None if code == 0 else "Crawl thất bại",
    })


@crawl_bp.route("/api/crawl/url", methods=["POST"])
def api_crawl_url():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Nhập URL"}), 400
    code, out = _run_script(
        "run_crawl_from_links.py",
        ["--mode", "url", "--url", url],
    )
    return jsonify({
        "ok": code == 0,
        "output": out,
        "error": None if code == 0 else "Crawl thất bại",
    })


@crawl_bp.route("/api/crawl/hierarchical", methods=["POST"])
def api_crawl_hierarchical():
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    max_pages = data.get("max", 500)
    if not url:
        return jsonify({"ok": False, "error": "Nhập URL gốc"}), 400
    code, out = _run_script(
        "crawl_hierarchical.py",
        [url, "--max", str(max_pages)],
    )
    return jsonify({
        "ok": code == 0,
        "output": out,
        "error": None if code == 0 else "Crawl thất bại",
    })


@crawl_bp.route("/api/crawl/links")
def api_list_links():
    if not LINKS_DIR.exists():
        return jsonify({"files": []})
    files = [f.name for f in LINKS_DIR.glob("*.json")]
    return jsonify({"files": files})
