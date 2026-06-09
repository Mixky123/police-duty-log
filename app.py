# -*- coding: utf-8 -*-
"""
app.py
เว็บแอปพลิเคชันหลัก (Flask) ของระบบจัดการเวรและบันทึกเหตุประจำวันของตำรวจ

หน้าที่ของไฟล์นี้:
- กำหนดเส้นทาง (routes) ของเว็บ เช่น /login, /dashboard, /officers ฯลฯ
- จัดการ session การเข้าสู่ระบบ (ใครเข้าระบบอยู่)
- รับข้อมูลจากฟอร์ม (request.form) ส่งต่อให้ชั้นฐานข้อมูล db.py
- ส่งข้อมูลไปแสดงผลผ่านเทมเพลต HTML (render_template)

โครงสร้างการเขียนโปรแกรมที่ใช้:
- ฟังก์ชัน, เงื่อนไข if/else, การวนซ้ำ (ในเทมเพลต)
- โครงสร้างข้อมูล dict / list
- การรับข้อมูลและแสดงผล (HTTP request/response)
- การจัดการฐานข้อมูลผ่านโมดูล db
"""

import os
import functools
import urllib.request
import json
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_file)
from datetime import datetime
import db


def get_ip_location(ip):
    """ดึง country/city จาก IP ผ่าน ip-api.com (ฟรี, ไม่ต้อง key)"""
    if not ip or ip in ("127.0.0.1", "::1"):
        return "Local"
    try:
        with urllib.request.urlopen(
            f"http://ip-api.com/json/{ip}?fields=country,city,status", timeout=2
        ) as r:
            data = json.loads(r.read())
        if data.get("status") == "success":
            return f"{data.get('city','')}, {data.get('country','')}"
    except Exception:
        pass
    return ""
from pdf_report import create_monthly_report_pdf
import law_data

app = Flask(__name__)
# คีย์ลับสำหรับเข้ารหัส session — ใช้ค่าจาก environment ถ้ามี (บนเซิร์ฟเวอร์จริง)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production")

# สร้าง/ตรวจสอบตารางฐานข้อมูลตั้งแต่ตอนเริ่มแอป
db.init_database()


# ----- ตัวช่วย: บังคับให้ต้องเข้าสู่ระบบก่อนเข้าหน้าอื่น -----
def login_required(view):
    """decorator สำหรับป้องกันหน้าที่ต้องเข้าสู่ระบบก่อน

    ถ้ายังไม่ได้ login จะถูกส่งกลับไปหน้า login อัตโนมัติ
    """
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบก่อนใช้งาน", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    """decorator สำหรับป้องกันหน้าที่ต้องเป็น admin เท่านั้น"""
    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("กรุณาเข้าสู่ระบบก่อนใช้งาน", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้ (Admin เท่านั้น)", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped_view


# ==========================================================
#  เส้นทางการยืนยันตัวตน (Authentication Routes)
# ==========================================================

@app.route("/")
def index():
    """หน้าแรก: ถ้า login แล้วไปแดชบอร์ด ถ้ายังให้ไปหน้า login"""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """หน้าเข้าสู่ระบบ รับ username/password ตรวจสอบกับฐานข้อมูล"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = db.verify_login(username, password)
        if user is None:
            db.add_login_log(username, "login_fail", False, request.remote_addr,
                             get_ip_location(request.remote_addr))
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        db.add_login_log(username, "login", True, request.remote_addr,
                         get_ip_location(request.remote_addr))
        flash("เข้าสู่ระบบสำเร็จ ยินดีต้อนรับ " + user["username"], "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """หน้าสมัครบัญชีผู้ใช้ใหม่"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()

        if password != confirm:
            flash("รหัสผ่านทั้งสองช่องไม่ตรงกัน", "warning")
            return redirect(url_for("register"))

        success, msg = db.register_user(username, password, role="officer")
        flash(msg, "success" if success else "danger")
        if success:
            return redirect(url_for("login"))
        return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    """ออกจากระบบ ล้าง session"""
    username = session.get("username", "")
    if username:
        db.add_login_log(username, "logout", True, request.remote_addr,
                         get_ip_location(request.remote_addr))
    session.clear()
    flash("ออกจากระบบเรียบร้อยแล้ว", "success")
    return redirect(url_for("login"))


# ==========================================================
#  เส้นทางแดชบอร์ด (Dashboard)
# ==========================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """หน้าแดชบอร์ดสรุปภาพรวม"""
    stats = db.get_dashboard_stats()
    # หาค่าสูงสุดของจำนวนเหตุการณ์ตามประเภท เพื่อคำนวณความยาวแถบกราฟ
    by_category = stats["by_category"]
    max_count = max(by_category.values()) if by_category else 1
    return render_template("dashboard.html", stats=stats, max_count=max_count)


# ==========================================================
#  เส้นทางจัดการเจ้าหน้าที่ (Officers)
# ==========================================================

@app.route("/officers")
@login_required
def officers():
    """แสดงรายชื่อเจ้าหน้าที่ทั้งหมด พร้อมการเรียงลำดับ"""
    sort_by = request.args.get("sort", "id")  # เรียงตาม: id, rank, full_name, badge_no, station
    order = request.args.get("order", "asc")  # asc หรือ desc

    all_officers = db.get_all_officers()

    # เรียงข้อมูล
    if sort_by == "rank":
        rank_order = ["พ.ต.อ.", "พ.ต.ท.", "พ.ต.ต.", "ร.ต.อ.", "ร.ต.ท.", "ร.ต.ต.",
                      "ด.ต.", "ส.ต.อ.", "ส.ต.ท.", "ส.ต.ต."]
        all_officers.sort(key=lambda x: rank_order.index(x['rank']) if x['rank'] in rank_order else 999)
    elif sort_by in ["full_name", "badge_no", "station"]:
        all_officers.sort(key=lambda x: x[sort_by] or "")
    else:
        all_officers.sort(key=lambda x: x['id'])

    if order == "desc":
        all_officers.reverse()

    return render_template("officers.html", officers=all_officers, sort_by=sort_by, order=order,
                           positions=law_data.POSITIONS, divisions=law_data.DIVISIONS,
                           executive_division=law_data.EXECUTIVE_DIVISION,
                           executive_positions=law_data.EXECUTIVE_POSITIONS)


@app.route("/officers/add", methods=["POST"])
@login_required
def officers_add():
    """เพิ่มเจ้าหน้าที่ใหม่ (รับข้อมูลจากฟอร์ม)"""
    success, msg = db.add_officer(
        request.form.get("rank", "").strip(),
        request.form.get("full_name", "").strip(),
        request.form.get("badge_no", "").strip(),
        request.form.get("phone", "").strip(),
        request.form.get("station", "").strip(),
        request.form.get("position", "").strip(),
    )
    flash(msg, "success" if success else "danger")
    return redirect(url_for("officers"))


@app.route("/officers/edit/<int:officer_id>", methods=["POST"])
@login_required
def officers_edit(officer_id):
    """แก้ไขข้อมูลเจ้าหน้าที่ตาม id"""
    success, msg = db.update_officer(
        officer_id,
        request.form.get("rank", "").strip(),
        request.form.get("full_name", "").strip(),
        request.form.get("badge_no", "").strip(),
        request.form.get("phone", "").strip(),
        request.form.get("station", "").strip(),
        request.form.get("position", "").strip(),
    )
    flash(msg, "success" if success else "danger")
    return redirect(url_for("officers"))


@app.route("/officers/delete/<int:officer_id>", methods=["POST"])
@login_required
def officers_delete(officer_id):
    """ลบเจ้าหน้าที่ตาม id"""
    success, msg = db.delete_officer(officer_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("officers"))


# ==========================================================
#  เส้นทางจัดการผู้ใช้ (Users) - Admin เท่านั้น
# ==========================================================

@app.route("/login-logs")
@admin_required
def login_logs():
    """หน้าดูประวัติการเข้าสู่ระบบ (Admin เท่านั้น)"""
    logs = db.get_login_logs(300)
    return render_template("login_logs.html", logs=logs)


@app.route("/users")
@admin_required
def users():
    """แสดงรายชื่อผู้ใช้ทั้งหมด (Admin เท่านั้น)"""
    all_users = db.get_all_users()
    return render_template("users.html", users=all_users)


@app.route("/users/add", methods=["POST"])
@admin_required
def users_add():
    """เพิ่มผู้ใช้ใหม่"""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "officer")

    success, msg = db.add_user(username, password, role)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("users"))


@app.route("/users/change-password/<int:user_id>", methods=["POST"])
@admin_required
def users_change_password(user_id):
    """เปลี่ยนรหัสผ่านผู้ใช้"""
    new_password = request.form.get("new_password", "").strip()
    success, msg = db.update_user_password(user_id, new_password)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("users"))


@app.route("/users/change-role/<int:user_id>", methods=["POST"])
@admin_required
def users_change_role(user_id):
    """เปลี่ยนบทบาทผู้ใช้"""
    role = request.form.get("role", "officer")
    success, msg = db.update_user_role(user_id, role)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("users"))


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def users_delete(user_id):
    """ลบผู้ใช้"""
    success, msg = db.delete_user(user_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("users"))


# ==========================================================
#  เส้นทางจัดการตารางเวร (Duties)
# ==========================================================

@app.route("/duties")
@login_required
def duties():
    """แสดงตารางเวรทั้งหมด พร้อมรายชื่อเจ้าหน้าที่สำหรับฟอร์มจัดเวร และการเรียงลำดับ"""
    sort_by = request.args.get("sort", "duty_date")  # เรียงตาม: duty_date, shift, status, officer_name
    order = request.args.get("order", "desc")  # asc หรือ desc

    all_duties = db.get_all_duties()
    all_officers = db.get_all_officers()

    # เรียงข้อมูล
    if sort_by == "duty_date":
        all_duties.sort(key=lambda x: x['duty_date'] or "")
    elif sort_by == "shift":
        shift_order = ["เช้า", "บ่าย", "ดึก"]
        all_duties.sort(key=lambda x: shift_order.index(x['shift']) if x['shift'] in shift_order else 999)
    elif sort_by == "status":
        status_order = ["scheduled", "in_progress", "completed", "absent"]
        all_duties.sort(key=lambda x: status_order.index(x['status']) if x['status'] in status_order else 999)
    elif sort_by == "officer_name":
        all_duties.sort(key=lambda x: x['officer_name'] or "")
    else:
        all_duties.sort(key=lambda x: x['id'])

    if order == "desc":
        all_duties.reverse()

    return render_template("duties.html", duties=all_duties, officers=all_officers, sort_by=sort_by, order=order)


@app.route("/duties/add", methods=["POST"])
@login_required
def duties_add():
    """เพิ่มการจัดเวรใหม่"""
    officer_id = request.form.get("officer_id", "")
    success, msg = db.add_duty(
        officer_id,
        request.form.get("duty_date", "").strip(),
        request.form.get("shift", "").strip(),
        request.form.get("location", "").strip(),
        request.form.get("status", "scheduled"),
        request.form.get("note", "").strip(),
    )
    flash(msg, "success" if success else "danger")
    return redirect(url_for("duties"))


@app.route("/duties/status/<int:duty_id>", methods=["POST"])
@login_required
def duties_status(duty_id):
    """อัปเดตสถานะเวร"""
    success, msg = db.update_duty_status(duty_id, request.form.get("status", "scheduled"))
    flash(msg, "success" if success else "danger")
    return redirect(url_for("duties"))


@app.route("/duties/delete/<int:duty_id>", methods=["POST"])
@login_required
def duties_delete(duty_id):
    """ลบรายการเวร"""
    success, msg = db.delete_duty(duty_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("duties"))


# ==========================================================
#  เส้นทางบันทึกเหตุประจำวัน (Incidents)
# ==========================================================

@app.route("/incidents")
@login_required
def incidents():
    """แสดงบันทึกเหตุการณ์ทั้งหมด พร้อมรายชื่อเจ้าหน้าที่สำหรับฟอร์ม และการเรียงลำดับ"""
    sort_by = request.args.get("sort", "incident_time")  # เรียงตาม: incident_time, category, status
    order = request.args.get("order", "desc")  # asc หรือ desc

    all_incidents = db.get_all_incidents()
    all_officers = db.get_all_officers()

    # เรียงข้อมูล
    if sort_by == "incident_time":
        all_incidents.sort(key=lambda x: x['incident_time'] or "")
    elif sort_by == "category":
        all_incidents.sort(key=lambda x: x['category'] or "")
    elif sort_by == "status":
        status_order = ["pending", "investigating", "resolved", "closed"]
        all_incidents.sort(key=lambda x: status_order.index(x['status']) if x['status'] in status_order else 999)
    elif sort_by == "officer_name":
        all_incidents.sort(key=lambda x: x['officer_name'] or "")
    else:
        all_incidents.sort(key=lambda x: x['id'])

    if order == "desc":
        all_incidents.reverse()

    return render_template("incidents.html",
                           incidents=all_incidents, officers=all_officers,
                           sort_by=sort_by, order=order,
                           laws=law_data.LAWS, law_names=law_data.LAW_NAMES)


@app.route("/incidents/add", methods=["POST"])
@login_required
def incidents_add():
    """เพิ่มบันทึกเหตุการณ์ใหม่"""
    officer_id = request.form.get("officer_id", "")
    # ถ้าไม่ได้เลือกเจ้าหน้าที่ ให้เก็บเป็น None
    if not officer_id:
        officer_id = None

    law = request.form.get("law", "").strip()
    section = request.form.get("section", "").strip()

    success, msg = db.add_incident(
        request.form.get("incident_time", "").strip(),
        law,  # category เก็บชื่อ พรบ เพื่อให้แดชบอร์ด/รายงานสรุปได้
        "",   # severity ถูกยกเลิกแล้ว (เก็บคอลัมน์ไว้เป็นค่าว่าง)
        request.form.get("location", "").strip(),
        request.form.get("description", "").strip(),
        officer_id,
        law,
        section,
    )
    flash(msg, "success" if success else "danger")
    return redirect(url_for("incidents"))


@app.route("/incidents/status/<int:incident_id>", methods=["POST"])
@login_required
def incidents_status(incident_id):
    """อัปเดตสถานะเหตุการณ์"""
    success, msg = db.update_incident_status(incident_id, request.form.get("status", "open"))
    flash(msg, "success" if success else "danger")
    return redirect(url_for("incidents"))


@app.route("/incidents/delete/<int:incident_id>", methods=["POST"])
@login_required
def incidents_delete(incident_id):
    """ลบบันทึกเหตุการณ์"""
    success, msg = db.delete_incident(incident_id)
    flash(msg, "success" if success else "danger")
    return redirect(url_for("incidents"))


# ==========================================================
#  เส้นทางสำหรับ Generate ข้อมูล (Data Generation) - Admin เท่านั้น
# ==========================================================

@app.route("/generate")
@admin_required
def generate():
    """หน้าสำหรับ generate ข้อมูลจำนวนมาก (Admin เท่านั้น)"""
    stats = db.get_dashboard_stats()
    return render_template("generate.html", stats=stats)


@app.route("/generate/officers", methods=["POST"])
@admin_required
def generate_officers():
    """Generate เจ้าหน้าที่จำนวนมาก (Admin เท่านั้น)"""
    count = request.form.get("count", "10")
    try:
        count = int(count)
        if count <= 0 or count > 100:
            flash("กรุณาระบุจำนวน 1-100 คน", "warning")
            return redirect(url_for("generate"))

        generated = db.generate_officers(count)
        flash(f"สร้างข้อมูลเจ้าหน้าที่สำเร็จ {generated} คน", "success")
    except ValueError:
        flash("กรุณาระบุจำนวนเป็นตัวเลข", "danger")

    return redirect(url_for("generate"))


@app.route("/generate/incidents", methods=["POST"])
@admin_required
def generate_incidents():
    """Generate เหตุการณ์จำนวนมาก (Admin เท่านั้น)"""
    """Generate เหตุการณ์จำนวนมาก"""
    count = request.form.get("count", "20")
    try:
        count = int(count)
        if count <= 0 or count > 200:
            flash("กรุณาระบุจำนวน 1-200 รายการ", "warning")
            return redirect(url_for("generate"))

        generated = db.generate_incidents(count)
        flash(f"สร้างข้อมูลเหตุการณ์สำเร็จ {generated} รายการ", "success")
    except ValueError:
        flash("กรุณาระบุจำนวนเป็นตัวเลข", "danger")

    return redirect(url_for("generate"))


# ==========================================================
#  เส้นทางสำหรับล้างข้อมูล (Clear Data) - Admin เท่านั้น
# ==========================================================

@app.route("/clear/officers", methods=["POST"])
@admin_required
def clear_officers():
    """ล้างข้อมูลเจ้าหน้าที่ทั้งหมด (Admin เท่านั้น)"""
    success, msg = db.delete_all_officers()
    flash(msg, "success" if success else "danger")
    return redirect(url_for("officers"))


@app.route("/clear/incidents", methods=["POST"])
@admin_required
def clear_incidents():
    """ล้างข้อมูลเหตุการณ์ทั้งหมด (Admin เท่านั้น)"""
    success, msg = db.delete_all_incidents()
    flash(msg, "success" if success else "danger")
    return redirect(url_for("incidents"))


# ==========================================================
#  เส้นทางสำหรับส่งออกรายงาน PDF (PDF Export)
# ==========================================================

@app.route("/reports")
@login_required
def reports():
    """หน้าสำหรับเลือกเดือน/ปี และส่งออกรายงาน PDF"""
    stats = db.get_dashboard_stats()
    return render_template("reports.html", stats=stats)


@app.route("/reports/export", methods=["POST"])
@login_required
def reports_export():
    """ส่งออกรายงาน PDF ตามเดือน/ปีที่เลือก"""
    year = request.form.get("year", "")
    month = request.form.get("month", "")

    try:
        year = int(year)
        month = int(month)

        if month < 1 or month > 12:
            flash("กรุณาเลือกเดือนที่ถูกต้อง (1-12)", "warning")
            return redirect(url_for("reports"))

        # ดึงข้อมูลเหตุการณ์ในเดือนที่เลือก
        incidents = db.get_incidents_by_month(year, month)

        if not incidents:
            flash(f"ไม่พบข้อมูลเหตุการณ์ในเดือน {month}/{year}", "warning")
            return redirect(url_for("reports"))

        # สร้าง PDF
        pdf_buffer = create_monthly_report_pdf(incidents, year, month)

        # ชื่อไฟล์
        thai_months = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                       "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        filename = f"รายงาน_{thai_months[month]}_{year+543}.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except ValueError:
        flash("กรุณาระบุปี/เดือนที่ถูกต้อง", "danger")
        return redirect(url_for("reports"))
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}", "danger")
        return redirect(url_for("reports"))


@app.route("/incidents/export-all", methods=["POST"])
@login_required
def incidents_export_all():
    """ส่งออกรายงาน PDF ของเหตุการณ์ทั้งหมดในระบบ"""
    try:
        all_incidents = db.get_all_incidents()

        if not all_incidents:
            flash("ไม่มีข้อมูลเหตุการณ์ในระบบ", "warning")
            return redirect(url_for("incidents"))

        # สร้าง PDF (ใช้เดือน/ปีปัจจุบัน สำหรับหัวรายงาน)
        from datetime import datetime
        now = datetime.now()
        pdf_buffer = create_monthly_report_pdf(all_incidents, now.year, now.month)

        filename = f"รายงานเหตุการณ์ทั้งหมด_{now.strftime('%Y%m%d')}.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการสร้างรายงาน: {str(e)}", "danger")
        return redirect(url_for("incidents"))


# ==========================================================
#  จุดเริ่มทำงานของแอป (สำหรับรันในเครื่อง)
# ==========================================================

if __name__ == "__main__":
    # บนเซิร์ฟเวอร์จริง gunicorn จะเป็นผู้เรียกใช้แอป (ไม่ผ่านบล็อกนี้)
    # ส่วนนี้ใช้สำหรับรันทดสอบในเครื่องเท่านั้น
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
