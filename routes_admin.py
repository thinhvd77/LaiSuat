import logging
import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from extensions import limiter
from models import db, Admin, Category, Pdf

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            login_user(admin)
            session.permanent = True
            logger.info("Admin login: %s", username)

            if admin.force_password_change:
                return redirect(url_for("admin.change_password"))
            return redirect(url_for("admin.dashboard"))

        flash("Sai tên đăng nhập hoặc mật khẩu", "error")

    return render_template("login.html")


@admin_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info("Admin logout: %s", current_user.username)
    logout_user()
    return redirect(url_for("admin.login"))


@admin_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    force = current_user.force_password_change

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Mật khẩu hiện tại không đúng", "error")
        elif new_password != confirm_password:
            flash("Mật khẩu mới không khớp", "error")
        elif len(new_password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự", "error")
        else:
            current_user.set_password(new_password)
            current_user.force_password_change = False
            db.session.commit()
            logger.info("Admin changed password: %s", current_user.username)
            flash("Đổi mật khẩu thành công", "success")
            return redirect(url_for("admin.dashboard"))

    return render_template("change_password.html", force=force)


@admin_bp.route("")
@login_required
def dashboard():
    if current_user.force_password_change:
        return redirect(url_for("admin.change_password"))
    return render_template("admin.html")


@admin_bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    data = request.get_json()
    if not data or not data.get("name"):
        return {"error": "Tên danh mục là bắt buộc"}, 400

    max_order = db.session.query(db.func.max(Category.sort_order)).scalar() or 0
    cat = Category(
        name=data["name"],
        icon=data.get("icon", "📄"),
        sort_order=max_order + 1,
    )
    db.session.add(cat)
    db.session.commit()
    logger.info("Category created: %s (by %s)", cat.name, current_user.username)
    return cat.to_dict(), 201


@admin_bp.route("/categories/<int:cat_id>", methods=["PUT"])
@login_required
def update_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    data = request.get_json()
    if data.get("name"):
        cat.name = data["name"]
    if data.get("icon"):
        cat.icon = data["icon"]
    if "sort_order" in data:
        cat.sort_order = data["sort_order"]

    db.session.commit()
    logger.info("Category updated: %s (by %s)", cat.name, current_user.username)
    return cat.to_dict(), 200


@admin_bp.route("/categories/<int:cat_id>", methods=["DELETE"])
@login_required
def delete_category(cat_id):
    cat = db.session.get(Category, cat_id)
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    if cat.pdfs.count() > 0:
        return {"error": "Không thể xóa danh mục còn tài liệu"}, 400

    db.session.delete(cat)
    db.session.commit()
    logger.info("Category deleted: %s (by %s)", cat.name, current_user.username)
    return {"message": "Đã xóa danh mục"}, 200


def _validate_pdf(file_storage):
    """Validate file is a PDF by extension and magic bytes."""
    if not file_storage or not file_storage.filename:
        return False, "Không có file"

    filename = file_storage.filename.lower()
    if not filename.endswith(".pdf"):
        return False, "Chỉ chấp nhận file PDF"

    # Check magic bytes
    header = file_storage.read(5)
    file_storage.seek(0)
    if header != b"%PDF-":
        return False, "Chỉ chấp nhận file PDF"

    return True, None


@admin_bp.route("/pdfs", methods=["POST"])
@login_required
def upload_pdf():
    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id")
    file = request.files.get("file")

    if not title:
        return {"error": "Tên tài liệu là bắt buộc"}, 400

    if not category_id:
        return {"error": "Danh mục là bắt buộc"}, 400

    cat = db.session.get(Category, int(category_id))
    if not cat:
        return {"error": "Không tìm thấy danh mục"}, 404

    valid, error_msg = _validate_pdf(file)
    if not valid:
        return {"error": error_msg}, 400

    # Sanitize filename with UUID prefix
    original = secure_filename(file.filename)
    safe_filename = f"{uuid.uuid4().hex[:8]}-{original}"

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], safe_filename)
    file.save(filepath)
    file_size = os.path.getsize(filepath)

    pdf = Pdf(
        category_id=cat.id,
        title=title,
        filename=safe_filename,
        file_size=file_size,
        uploaded_by=current_user.id,
    )
    db.session.add(pdf)
    db.session.commit()

    logger.info(
        "PDF uploaded: %s → %s (by %s)",
        title,
        safe_filename,
        current_user.username,
    )
    return pdf.to_dict(), 201


@admin_bp.route("/pdfs/<int:pdf_id>", methods=["DELETE"])
@login_required
def delete_pdf(pdf_id):
    pdf = db.session.get(Pdf, pdf_id)
    if not pdf:
        return {"error": "Không tìm thấy tài liệu"}, 404

    # Remove file from disk
    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], pdf.filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    logger.info(
        "PDF deleted: %s / %s (by %s)",
        pdf.title,
        pdf.filename,
        current_user.username,
    )
    db.session.delete(pdf)
    db.session.commit()

    return {"message": "Đã xóa tài liệu"}, 200
