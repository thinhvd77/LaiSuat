import os
import logging

from flask import Blueprint, render_template, send_file, current_app

from models import db, Category, Pdf

logger = logging.getLogger(__name__)

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/api/categories")
def list_categories():
    categories = Category.query.order_by(Category.sort_order.asc()).all()
    return [cat.to_dict() for cat in categories]


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
