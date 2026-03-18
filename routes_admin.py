import logging

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user

from models import db, Admin

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
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
