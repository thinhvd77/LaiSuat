import os
import hmac
import logging

from flask import Blueprint, render_template, send_file, current_app, request, redirect, url_for, session

from extensions import db
from models import Category, Pdf
from site_gate import (
    is_ip_locked,
    record_failed_attempt,
    reset_ip_lock_state,
    set_session_unlocked,
    lockout_message,
    render_gate_page,
)
from site_gate import get_site_gate_ip

logger = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/api/categories")
def list_categories():
    parents = (
        Category.query
        .filter(Category.parent_id.is_(None))
        .order_by(Category.sort_order.asc())
        .all()
    )
    return [p.to_dict() for p in parents]


@public_bp.route("/api/categories/<int:cat_id>/pdfs")
def list_pdfs(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    pdfs = (
        Pdf.query.filter_by(category_id=cat_id)
        .order_by(Pdf.uploaded_at.desc())
        .all()
    )
    return [pdf.to_dict() for pdf in pdfs]


@public_bp.route("/pdf/<int:pdf_id>")
def serve_pdf(pdf_id):
    pdf = db.session.get(Pdf, pdf_id)
    if not pdf:
        return {"error": "Không tìm thấy tài liệu"}, 404

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], pdf.filename)
    if not os.path.exists(filepath):
        logger.warning("PDF file missing from disk: %s", pdf.filename)
        return {"error": "Không tìm thấy tài liệu"}, 404

    return send_file(
        filepath,
        mimetype="application/pdf",
        download_name=pdf.filename,
        as_attachment=False,
    )


@public_bp.route("/gate/unlock", methods=["POST"])
def gate_unlock():
    if not current_app.config.get("SITE_GATE_ENABLED", False):
        return redirect(url_for("public.index"))

    expected_password = current_app.config.get("SITE_GATE_PASSWORD", "")
    if not expected_password:
        return render_gate_page(
            gate_error="Hệ thống chưa cấu hình mật khẩu truy cập. Vui lòng liên hệ quản trị viên.",
            locked_seconds=0,
            status_code=403,
        )

    ip = get_site_gate_ip()
    locked, seconds_left = is_ip_locked(ip)
    if locked:
        return render_gate_page(
            gate_error=lockout_message(),
            locked_seconds=seconds_left,
            status_code=403,
        )

    input_password = request.form.get("password", "")
    if hmac.compare_digest(input_password, expected_password):
        reset_ip_lock_state(ip)
        ttl = int(current_app.config.get("SITE_GATE_TTL_MINUTES", 1440))
        set_session_unlocked(ttl)
        session.permanent = True
        return redirect(url_for("public.index"))

    locked, seconds_left = record_failed_attempt(ip)
    if locked:
        return render_gate_page(
            gate_error=lockout_message(),
            locked_seconds=seconds_left,
            status_code=403,
        )

    return render_gate_page(
        gate_error="Mật khẩu không đúng",
        locked_seconds=0,
        status_code=200,
    )
