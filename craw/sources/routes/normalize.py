"""
Router Normalize - Trang và API xử lý dữ liệu
Chọn folder trong /data → output: nor/{name}_nor (trong thư mục nor)
VD: data/ptits → nor/ptits_nor
"""
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify

from sources.services.normalize_service import run_normalize, PROCESSOR_KEYS

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_BASES = [
    ("public/data", ROOT / "public" / "data"),
    ("sources/scripts/data", ROOT / "sources" / "scripts" / "data"),
]
# Map data base → nor base (output nằm trong nor)
NOR_BY_DATA = {
    ROOT / "public" / "data": ROOT / "public" / "nor",
    ROOT / "sources" / "scripts" / "data": ROOT / "sources" / "nor",
}

normalize_bp = Blueprint("normalize", __name__, url_prefix="")


def _get_output_path(input_path: Path) -> Path:
    """Output folder = nor/{tên_folder}_nor (trong thư mục nor)."""
    for data_base, nor_base in NOR_BY_DATA.items():
        try:
            if input_path == data_base or (data_base in input_path.parents):
                folder_name = input_path.name
                return nor_base / f"{folder_name}_nor"
        except ValueError:
            continue
    return input_path.parent / f"{input_path.name}_nor"


def _list_folders(base: Path) -> list[tuple[str, Path]]:
    """Liệt kê folder có file .md/.txt trong /data (bao gồm chính base nếu có file)."""
    out = []
    if not base.exists():
        return out
    base_count = len(list(base.glob("*.md"))) + len(list(base.glob("*.txt")))
    if base_count > 0:
        out.append((str(base.relative_to(ROOT)), base))
    for d in sorted(base.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and not d.name.endswith("_nor"):
            count = len(list(d.glob("*.md"))) + len(list(d.glob("*.txt")))
            if count > 0:
                out.append((str(d.relative_to(ROOT)), d))
    return out


def _list_files(folder: Path) -> list[str]:
    return sorted(
        f.name for f in folder.iterdir()
        if f.is_file() and f.suffix in (".md", ".txt") and not f.name.startswith(".")
    )


@normalize_bp.route("/normalize")
def normalize_page():
    folders = []
    for label, base in DATA_BASES:
        for rel, path in _list_folders(base):
            count = len(_list_files(path)) if path.exists() else 0
            output_rel = str(_get_output_path(path).relative_to(ROOT))
            folders.append({
                "label": rel,
                "path": rel,
                "count": count,
                "output": output_rel,
            })
    return render_template(
        "normalize.html",
        folders=folders,
        processors=PROCESSOR_KEYS,
    )


@normalize_bp.route("/api/normalize/folders")
def api_folders():
    result = []
    for label, base in DATA_BASES:
        for rel, path in _list_folders(base):
            result.append({"path": rel, "label": rel, "output": str(_get_output_path(path).relative_to(ROOT))})
    return jsonify({"folders": result})


@normalize_bp.route("/api/normalize/files")
def api_files():
    folder = request.args.get("folder", "")
    if not folder:
        return jsonify({"files": []})
    path = ROOT / folder
    if not path.exists() or not path.is_dir():
        return jsonify({"files": []})
    return jsonify({"files": _list_files(path)})


@normalize_bp.route("/api/normalize/run", methods=["POST"])
def api_normalize_run():
    data = request.get_json() or {}
    folder = (data.get("folder") or "").strip()
    file_name = (data.get("file") or "").strip() or None
    mode = "file" if file_name else "folder"
    steps = data.get("steps") or PROCESSOR_KEYS

    if not folder:
        return jsonify({"ok": False, "output": "Chọn folder trong /data", "stats": {}}), 400

    input_path = ROOT / folder
    if not input_path.exists():
        return jsonify({"ok": False, "output": "Folder không tồn tại", "stats": {}}), 400

    # Output: nor/{name}_nor
    output_path = _get_output_path(input_path)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        result = run_normalize(
            input_dir=input_path,
            output_dir=output_path,
            mode=mode,
            file_name=file_name,
            steps=steps,
        )
        result["output_folder"] = str(output_path.relative_to(ROOT))
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "output": str(e), "stats": {}}), 500
