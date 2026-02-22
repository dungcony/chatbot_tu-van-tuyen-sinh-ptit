"""
Router Prepare - Trang và API upload dữ liệu lên MongoDB
Bao gồm: nor/ cũ, data/, và các folder *_nor (kết quả normalize)
"""
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify

from sources.services.prepare_service import run_prepare

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_BASES = [
    ("public/data", ROOT / "public" / "data"),
    ("sources/scripts/data", ROOT / "sources" / "scripts" / "data"),
]
NOR_DIRS = [
    ("public/nor", ROOT / "public" / "nor"),
    ("sources/nor", ROOT / "sources" / "nor"),
]

prepare_bp = Blueprint("prepare", __name__, url_prefix="")


def _list_folders_with_md(base: Path) -> list[tuple[str, Path]]:
    """Liệt kê folder có file .md (bao gồm base và subfolder)."""
    out = []
    if not base.exists():
        return out
    base_count = len(list(base.glob("*.md")))
    if base_count > 0:
        out.append((str(base.relative_to(ROOT)), base))
    for d in sorted(base.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            count = len(list(d.glob("*.md")))
            if count > 0:
                out.append((str(d.relative_to(ROOT)), d))
    return out


@prepare_bp.route("/prepare")
def prepare_page():
    dirs = []
    # Thư mục nor (bao gồm nor và các subfolder *_nor bên trong)
    for label, path in NOR_DIRS:
        if path.exists():
            for rel, p in _list_folders_with_md(path):
                count = len(list(p.glob("*.md")))
                dirs.append({"label": rel, "path": str(p), "count": count})
    # Thư mục data và các folder *_nor bên trong
    for label, base in DATA_BASES:
        for rel, path in _list_folders_with_md(base):
            count = len(list(path.glob("*.md")))
            dirs.append({"label": rel, "path": str(path), "count": count})
    return render_template("prepare.html", source_dirs=dirs)


@prepare_bp.route("/api/prepare/run", methods=["POST"])
def api_prepare_run():
    data = request.get_json() or {}
    source = (data.get("source") or "").strip()
    clear_first = data.get("clear", False)
    embed_after = data.get("embed", True)

    if not source:
        return jsonify({"ok": False, "error": "Chọn nguồn"}), 400

    path = Path(source)
    if not path.exists() or not path.is_dir():
        return jsonify({"ok": False, "error": "Folder không tồn tại"}), 400

    try:
        result = run_prepare(path, clear_first=clear_first, embed_after=embed_after)
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "uploaded": 0, "files": 0, "embedded": 0}), 500
