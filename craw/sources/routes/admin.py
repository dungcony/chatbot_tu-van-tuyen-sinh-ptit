"""
Admin routes - Trang và API quản lý documents TVTS
"""
from flask import Blueprint, render_template, request, jsonify
from bson import ObjectId

from sources.models.document import get_collection

admin_bp = Blueprint("admin", __name__)


def doc_to_dict(doc):
    d = dict(doc)
    d["_id"] = str(d["_id"])
    return d


# ─── Trang ───────────────────────────────────────────────────────────────


@admin_bp.route("/")
@admin_bp.route("/admin")
def admin_page():
    return render_template("admin.html")


# ─── API ─────────────────────────────────────────────────────────────────


@admin_bp.route("/api/stats")
def api_stats():
    col = get_collection()
    total = col.count_documents({})
    schools = col.distinct("school")
    school_counts = {s: col.count_documents({"school": s}) for s in schools if s}
    return jsonify({
        "total_documents": total,
        "schools": school_counts,
        "school_list": [s for s in schools if s],
    })


@admin_bp.route("/api/documents")
def api_list_documents():
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 100)
    school = request.args.get("school", "").strip() or None
    search = request.args.get("search", "").strip() or None
    source_file = request.args.get("source_file", "").strip() or None

    col = get_collection()
    q = {}
    if school:
        q["school"] = school
    if source_file:
        q["source_file"] = {"$regex": source_file, "$options": "i"}
    if search:
        q["$or"] = [
            {"content": {"$regex": search, "$options": "i"}},
            {"source_title": {"$regex": search, "$options": "i"}},
            {"source_file": {"$regex": search, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = col.count_documents(q)
    cursor = col.find(q).sort("_id", -1).skip(skip).limit(limit)
    docs = [doc_to_dict(d) for d in cursor]
    return jsonify({
        "documents": docs,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
    })


@admin_bp.route("/api/documents/<doc_id>")
def api_get_document(doc_id):
    col = get_collection()
    try:
        doc = col.find_one({"_id": ObjectId(doc_id)})
    except Exception:
        return jsonify({"detail": "ID không hợp lệ"}), 400
    if not doc:
        return jsonify({"detail": "Không tìm thấy document"}), 404
    return jsonify(doc_to_dict(doc))


@admin_bp.route("/api/documents/<doc_id>", methods=["PUT"])
def api_update_document(doc_id):
    data = request.get_json() or {}
    update_data = {k: v for k, v in data.items() if v is not None and k in (
        "content", "school", "source_file", "source_url", "source_title",
        "tags", "chunk_id", "total_chunks"
    )}
    if not update_data:
        return jsonify({"detail": "Không có dữ liệu cập nhật"}), 400

    col = get_collection()
    try:
        result = col.update_one({"_id": ObjectId(doc_id)}, {"$set": update_data})
    except Exception:
        return jsonify({"detail": "ID không hợp lệ"}), 400
    if result.matched_count == 0:
        return jsonify({"detail": "Không tìm thấy document"}), 404
    return jsonify({"ok": True, "message": "Đã cập nhật"})


@admin_bp.route("/api/documents/<doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    col = get_collection()
    try:
        result = col.delete_one({"_id": ObjectId(doc_id)})
    except Exception:
        return jsonify({"detail": "ID không hợp lệ"}), 400
    if result.deleted_count == 0:
        return jsonify({"detail": "Không tìm thấy document"}), 404
    return jsonify({"ok": True, "message": "Đã xóa"})


@admin_bp.route("/api/documents", methods=["POST"])
def api_create_document():
    data = request.get_json() or {}
    content = data.get("content")
    if not content:
        return jsonify({"detail": "Nội dung bắt buộc"}), 400

    doc = {
        "content": content,
        "school": data.get("school"),
        "source_file": data.get("source_file"),
        "source_url": data.get("source_url"),
        "source_title": data.get("source_title"),
        "tags": data.get("tags") or [],
        "chunk_id": data.get("chunk_id"),
        "total_chunks": data.get("total_chunks"),
        "embedding": None,
    }
    doc = {k: v for k, v in doc.items() if v is not None}
    col = get_collection()
    result = col.insert_one(doc)
    return jsonify({"ok": True, "id": str(result.inserted_id), "message": "Đã tạo mới"})
