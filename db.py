# -*- coding: utf-8 -*-
"""
db.py
ชั้นจัดการฐานข้อมูล (Data Access Layer) ของระบบจัดการเวรและบันทึกเหตุประจำวันของตำรวจ

จุดเด่น: รองรับฐานข้อมูล 2 แบบด้วยโค้ดชุดเดียว
  - PostgreSQL  : ใช้เมื่อ deploy ขึ้นออนไลน์ (Render) ผ่าน environment variable DATABASE_URL
  - SQLite      : ใช้เมื่อรันทดสอบในเครื่อง (ไม่ต้องตั้งค่าอะไรเพิ่ม)

ระบบจะตรวจว่ามี DATABASE_URL หรือไม่ ถ้ามี = ใช้ Postgres, ถ้าไม่มี = ใช้ SQLite
ทำให้พัฒนาในเครื่องและใช้งานจริงบนเว็บได้ด้วยซอร์สโค้ดเดียวกัน

โครงสร้างการเขียนโปรแกรมที่ใช้:
- ตัวแปรและชนิดข้อมูล, ฟังก์ชัน, เงื่อนไข if/else, การวนซ้ำ for
- โครงสร้างข้อมูล list / dict
- การจัดการฐานข้อมูล (CREATE/INSERT/SELECT/UPDATE/DELETE) และการจัดการข้อผิดพลาด try/except
"""

import os
import hashlib
from datetime import datetime

# ตรวจว่ามีการตั้งค่า DATABASE_URL (Postgres) หรือไม่
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    # Render บางครั้งให้ URL ขึ้นต้นด้วย postgres:// ซึ่ง psycopg2 รุ่นใหม่ต้องการ postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    import sqlite3
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "police_duty.db")

# PLACEHOLDER ของพารามิเตอร์ใน SQL ต่างกันระหว่างสองฐานข้อมูล
#   Postgres ใช้ %s , SQLite ใช้ ?
PH = "%s" if USE_POSTGRES else "?"


def get_connection():
    """สร้างและคืนค่า connection ไปยังฐานข้อมูลที่ใช้งานอยู่

    คืน connection ที่อ่านผลลัพธ์เป็น dict ได้ (เข้าถึงด้วยชื่อคอลัมน์)
    ทั้งสองฐานข้อมูล
    """
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        # timeout=10 ให้รอได้ถ้าฐานข้อมูลถูกล็อกชั่วคราว (กรณีหลาย connection พร้อมกัน)
        conn = sqlite3.connect(SQLITE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        # WAL mode ช่วยให้อ่าน/เขียนพร้อมกันได้ดีขึ้นบน SQLite
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn


def _dict_cursor(conn):
    """คืน cursor ที่อ่านแถวเป็น dict ได้ (เฉพาะ Postgres ต้องระบุ cursor_factory)"""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def _row_to_dict(row):
    """แปลงผลลัพธ์หนึ่งแถวให้เป็น dict ปกติ (รองรับทั้งสองฐานข้อมูล)"""
    if row is None:
        return None
    return dict(row)


def hash_password(password):
    """เข้ารหัสรหัสผ่านด้วย SHA-256 (ไม่เก็บรหัสผ่านเป็น plain text)"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def now_str():
    """คืนค่าเวลาปัจจุบันเป็นข้อความรูปแบบมาตรฐาน"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_database():
    """สร้างตารางทั้งหมดหากยังไม่มี และสร้างบัญชีผู้ดูแลเริ่มต้น

    ใช้ชนิดข้อมูลที่ทำงานได้ทั้ง Postgres และ SQLite:
      - คีย์หลักแบบ auto-increment เขียนต่างกันเล็กน้อยจึงเลือกตามฐานข้อมูล
    """
    # นิยามคีย์หลักแบบเพิ่มอัตโนมัติ ต่างกันระหว่างสองฐานข้อมูล
    if USE_POSTGRES:
        pk = "SERIAL PRIMARY KEY"
    else:
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT"

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            id            {pk},
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'officer',
            created_at    TEXT NOT NULL
        );
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS officers (
            id         {pk},
            rank       TEXT NOT NULL,
            full_name  TEXT NOT NULL,
            badge_no   TEXT NOT NULL UNIQUE,
            phone      TEXT,
            station    TEXT,
            created_at TEXT NOT NULL
        );
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS duties (
            id          {pk},
            officer_id  INTEGER NOT NULL REFERENCES officers(id) ON DELETE CASCADE,
            duty_date   TEXT NOT NULL,
            shift       TEXT NOT NULL,
            location    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'scheduled',
            note        TEXT,
            created_at  TEXT NOT NULL
        );
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS incidents (
            id            {pk},
            incident_time TEXT NOT NULL,
            category      TEXT NOT NULL,
            severity      TEXT NOT NULL,
            location      TEXT NOT NULL,
            description   TEXT NOT NULL,
            officer_id    INTEGER REFERENCES officers(id) ON DELETE SET NULL,
            status        TEXT NOT NULL DEFAULT 'open',
            created_at    TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
    _ensure_default_admin()


def _ensure_default_admin():
    """สร้างบัญชีผู้ดูแลเริ่มต้น (admin/admin123) หากยังไม่มีผู้ใช้ในระบบ"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users;")
    count = cur.fetchone()[0]
    if count == 0:
        cur.execute(
            f"INSERT INTO users (username, password_hash, role, created_at) VALUES ({PH}, {PH}, {PH}, {PH});",
            ("admin", hash_password("admin123"), "admin", now_str()),
        )
        conn.commit()
    conn.close()


# ==========================================================
#  ส่วนที่ 1 : การยืนยันตัวตนผู้ใช้ (Authentication)
# ==========================================================

def verify_login(username, password):
    """ตรวจสอบ username/password คืน dict ผู้ใช้ถ้าถูกต้อง มิฉะนั้นคืน None"""
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute(f"SELECT * FROM users WHERE username = {PH};", (username,))
    row = _row_to_dict(cur.fetchone())
    conn.close()
    if row is None:
        return None
    if row["password_hash"] == hash_password(password):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def register_user(username, password, role="officer"):
    """สมัครบัญชีผู้ใช้ใหม่ คืน (สำเร็จ, ข้อความ)"""
    if not username or not password:
        return False, "กรุณากรอกชื่อผู้ใช้และรหัสผ่านให้ครบ"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO users (username, password_hash, role, created_at) VALUES ({PH}, {PH}, {PH}, {PH});",
            (username, hash_password(password), role, now_str()),
        )
        conn.commit()
        conn.close()
        return True, "สมัครบัญชีผู้ใช้สำเร็จ"
    except Exception as e:
        # ทั้ง psycopg2 และ sqlite3 จะ raise error เมื่อ username ซ้ำ (UNIQUE)
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False, "ชื่อผู้ใช้นี้มีอยู่แล้วในระบบ"
        return False, "เกิดข้อผิดพลาด: " + str(e)


# ==========================================================
#  ส่วนที่ 2 : จัดการข้อมูลเจ้าหน้าที่ (Officers CRUD)
# ==========================================================

def add_officer(rank, full_name, badge_no, phone, station):
    """เพิ่มข้อมูลเจ้าหน้าที่ใหม่ คืน (สำเร็จ, ข้อความ)"""
    if not rank or not full_name or not badge_no:
        return False, "กรุณากรอก ยศ ชื่อ-สกุล และเลขประจำตัวให้ครบ"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO officers (rank, full_name, badge_no, phone, station, created_at)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH});""",
            (rank, full_name, badge_no, phone, station, now_str()),
        )
        conn.commit()
        conn.close()
        return True, "บันทึกข้อมูลเจ้าหน้าที่สำเร็จ"
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False, "เลขประจำตัว (Badge No.) นี้มีอยู่แล้วในระบบ"
        return False, "เกิดข้อผิดพลาด: " + str(e)


def get_all_officers():
    """ดึงรายชื่อเจ้าหน้าที่ทั้งหมด คืน list ของ dict"""
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute("SELECT * FROM officers ORDER BY id;")
    rows = [_row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_officer(officer_id):
    """ดึงข้อมูลเจ้าหน้าที่รายเดียวตาม id"""
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute(f"SELECT * FROM officers WHERE id = {PH};", (officer_id,))
    row = _row_to_dict(cur.fetchone())
    conn.close()
    return row


def update_officer(officer_id, rank, full_name, badge_no, phone, station):
    """แก้ไขข้อมูลเจ้าหน้าที่ตาม id"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""UPDATE officers
                SET rank = {PH}, full_name = {PH}, badge_no = {PH}, phone = {PH}, station = {PH}
                WHERE id = {PH};""",
            (rank, full_name, badge_no, phone, station, officer_id),
        )
        conn.commit()
        conn.close()
        return True, "แก้ไขข้อมูลเจ้าหน้าที่สำเร็จ"
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return False, "เลขประจำตัว (Badge No.) นี้มีอยู่แล้วในระบบ"
        return False, "เกิดข้อผิดพลาด: " + str(e)


def delete_officer(officer_id):
    """ลบข้อมูลเจ้าหน้าที่ตาม id"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM officers WHERE id = {PH};", (officer_id,))
        conn.commit()
        conn.close()
        return True, "ลบข้อมูลเจ้าหน้าที่สำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


# ==========================================================
#  ส่วนที่ 3 : จัดการตารางเวร (Duties CRUD)
# ==========================================================

def add_duty(officer_id, duty_date, shift, location, status, note):
    """เพิ่มการจัดเวรใหม่"""
    if not officer_id or not duty_date or not shift or not location:
        return False, "กรุณาเลือกเจ้าหน้าที่ และกรอกวันที่ ผลัด สถานที่ ให้ครบ"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO duties (officer_id, duty_date, shift, location, status, note, created_at)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, {PH});""",
            (officer_id, duty_date, shift, location, status, note, now_str()),
        )
        conn.commit()
        conn.close()
        return True, "บันทึกตารางเวรสำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


def get_all_duties():
    """ดึงตารางเวรทั้งหมด พร้อมชื่อเจ้าหน้าที่ (JOIN)"""
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute("""
        SELECT d.id, d.duty_date, d.shift, d.location, d.status, d.note,
               o.rank AS officer_rank, o.full_name AS officer_name, o.id AS officer_id
        FROM duties d
        JOIN officers o ON d.officer_id = o.id
        ORDER BY d.duty_date DESC, d.shift;
    """)
    rows = [_row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_duty_status(duty_id, status):
    """อัปเดตสถานะของเวร"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE duties SET status = {PH} WHERE id = {PH};", (status, duty_id))
        conn.commit()
        conn.close()
        return True, "อัปเดตสถานะเวรสำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


def delete_duty(duty_id):
    """ลบรายการเวรตาม id"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM duties WHERE id = {PH};", (duty_id,))
        conn.commit()
        conn.close()
        return True, "ลบรายการเวรสำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


# ==========================================================
#  ส่วนที่ 4 : บันทึกเหตุประจำวัน (Incidents CRUD)
# ==========================================================

def add_incident(incident_time, category, severity, location, description, officer_id):
    """เพิ่มบันทึกเหตุการณ์ใหม่ (officer_id อาจเป็น None ได้)"""
    if not incident_time or not category or not location or not description:
        return False, "กรุณากรอก เวลา ประเภท สถานที่ และรายละเอียดให้ครบ"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO incidents
                (incident_time, category, severity, location, description, officer_id, status, created_at)
                VALUES ({PH}, {PH}, {PH}, {PH}, {PH}, {PH}, 'open', {PH});""",
            (incident_time, category, severity, location, description, officer_id, now_str()),
        )
        conn.commit()
        conn.close()
        return True, "บันทึกเหตุการณ์สำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


def get_all_incidents():
    """ดึงบันทึกเหตุการณ์ทั้งหมด พร้อมชื่อเจ้าหน้าที่ผู้บันทึก (LEFT JOIN)"""
    conn = get_connection()
    cur = _dict_cursor(conn)
    cur.execute("""
        SELECT i.id, i.incident_time, i.category, i.severity, i.location,
               i.description, i.status, o.full_name AS officer_name
        FROM incidents i
        LEFT JOIN officers o ON i.officer_id = o.id
        ORDER BY i.incident_time DESC;
    """)
    rows = [_row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_incident_status(incident_id, status):
    """อัปเดตสถานะเหตุการณ์"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"UPDATE incidents SET status = {PH} WHERE id = {PH};", (status, incident_id))
        conn.commit()
        conn.close()
        return True, "อัปเดตสถานะเหตุการณ์สำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


def delete_incident(incident_id):
    """ลบบันทึกเหตุการณ์ตาม id"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM incidents WHERE id = {PH};", (incident_id,))
        conn.commit()
        conn.close()
        return True, "ลบบันทึกเหตุการณ์สำเร็จ"
    except Exception as e:
        return False, "เกิดข้อผิดพลาด: " + str(e)


# ==========================================================
#  ส่วนที่ 5 : สถิติสำหรับหน้าแดชบอร์ด (Statistics)
# ==========================================================

def get_dashboard_stats():
    """รวบรวมตัวเลขสรุปสำหรับหน้าแดชบอร์ด คืนค่าเป็น dict

    ใช้ COUNT และ GROUP BY ของ SQL ร่วมกับการวนซ้ำ (for loop)
    เพื่อสรุปจำนวนเหตุการณ์แยกตามประเภทและระดับความรุนแรง
    """
    conn = get_connection()
    cur = conn.cursor()
    stats = {}

    cur.execute("SELECT COUNT(*) FROM officers;")
    stats["total_officers"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM duties;")
    stats["total_duties"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM incidents;")
    stats["total_incidents"] = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM incidents WHERE status != 'closed';")
    stats["open_incidents"] = cur.fetchone()[0]

    # สรุปจำนวนเหตุการณ์แยกตามประเภท -> เก็บใน dict (ใช้ for loop)
    cur.execute("SELECT category, COUNT(*) FROM incidents GROUP BY category ORDER BY COUNT(*) DESC;")
    by_category = {}
    for row in cur.fetchall():
        by_category[row[0]] = row[1]
    stats["by_category"] = by_category

    # สรุปจำนวนเหตุการณ์แยกตามระดับความรุนแรง
    cur.execute("SELECT severity, COUNT(*) FROM incidents GROUP BY severity;")
    by_severity = {}
    for row in cur.fetchall():
        by_severity[row[0]] = row[1]
    stats["by_severity"] = by_severity

    conn.close()
    return stats


# ==========================================================
#  ส่วนที่ 6 : Generate ข้อมูลจำนวนมาก (Bulk Data Generation)
# ==========================================================

def generate_officers(count=10):
    """สร้างเจ้าหน้าที่สุ่มจำนวน count คน"""
    import random
    ranks = ["พ.ต.อ.", "พ.ต.ท.", "พ.ต.ต.", "ร.ต.อ.", "ร.ต.ท.", "ร.ต.ต.",
             "ด.ต.", "ส.ต.อ.", "ส.ต.ท.", "ส.ต.ต."]
    first_names = ["สมชาย", "วิชัย", "ประสงค์", "อนุชา", "ธนากร", "ณัฐพล",
                   "สมศักดิ์", "วีระ", "ชัยวัฒน์", "พิชัย", "เกรียงไกร", "สุรชัย"]
    last_names = ["ใจเด็ด", "รักษาชาติ", "มั่นคง", "กล้าหาญ", "สุจริต", "อดทน",
                  "ซื่อตรง", "ยุติธรรม", "เข้มแข็ง", "รักษาดี", "ปกป้อง", "ดีงาม"]
    stations = ["สภ.เมือง", "สภ.คลองหลวง", "สภ.ธัญบุรี", "สภ.รังสิต", "สภ.ลำลูกกา"]

    generated = 0
    for i in range(count):
        rank = random.choice(ranks)
        fname = random.choice(first_names)
        lname = random.choice(last_names)
        badge = f"P{random.randint(2000, 9999)}"
        phone = f"08{random.randint(0,9)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        station = random.choice(stations)

        success, msg = add_officer(rank, f"{fname} {lname}", badge, phone, station)
        if success:
            generated += 1

    return generated


def generate_incidents(count=20):
    """สร้างเหตุการณ์สุ่มจำนวน count รายการ"""
    import random
    from datetime import datetime, timedelta

    categories = ["อุบัติเหตุจราจร", "ลักทรัพย์", "ทะเลาะวิวาท", "ยาเสพติด",
                  "เหตุทั่วไป", "ทำร้ายร่างกาย", "รถหาย", "วิ่งราว"]
    severities = ["ต่ำ", "ปานกลาง", "สูง", "วิกฤต"]
    locations = ["สี่แยกกลางเมือง", "ตลาดนัด", "ห้างสรรพสินค้า", "สวนสาธารณะ",
                 "ถนนหน้าตลาด", "ลานจอดรถห้าง", "ย่านที่พักอาศัย", "ริมถนนใหญ่"]

    # ดึงรายชื่อเจ้าหน้าที่มาสุ่ม
    officers = get_all_officers()
    if not officers:
        return 0

    generated = 0
    for i in range(count):
        # สุ่มเวลาย้อนหลัง 30 วัน
        days_ago = random.randint(0, 30)
        hours = random.randint(0, 23)
        minutes = random.randint(0, 59)
        incident_time = datetime.now() - timedelta(days=days_ago, hours=hours, minutes=minutes)
        time_str = incident_time.strftime("%Y-%m-%d %H:%M")

        category = random.choice(categories)
        severity = random.choice(severities)
        location = random.choice(locations)
        description = f"เหตุการณ์ {category} เกิดขึ้นที่ {location}"
        officer_id = random.choice(officers)["id"]

        success, msg = add_incident(time_str, category, severity, location, description, officer_id)
        if success:
            generated += 1

    return generated


# ==========================================================
#  ส่วนที่ 7 : ดึงข้อมูลเหตุการณ์ตามเดือน (Monthly Report)
# ==========================================================

def get_incidents_by_month(year, month):
    """ดึงเหตุการณ์ทั้งหมดในเดือนที่กำหนด คืน list ของ dict"""
    conn = get_connection()
    cur = _dict_cursor(conn)

    # สร้างช่วงวันที่ของเดือน
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1}-01-01"
    else:
        end_date = f"{year}-{month+1:02d}-01"

    cur.execute(f"""
        SELECT i.*, o.rank, o.full_name AS officer_name
        FROM incidents i
        LEFT JOIN officers o ON i.officer_id = o.id
        WHERE i.incident_time >= {PH} AND i.incident_time < {PH}
        ORDER BY i.incident_time DESC;
    """, (start_date, end_date))

    rows = [_row_to_dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# รันไฟล์นี้โดยตรงเพื่อสร้าง/ตรวจสอบฐานข้อมูล
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    init_database()
    backend = "PostgreSQL (online)" if USE_POSTGRES else "SQLite (local)"
    print("สร้าง/ตรวจสอบฐานข้อมูลเรียบร้อยแล้ว | ใช้ฐานข้อมูล:", backend)
    print("บัญชีผู้ดูแลเริ่มต้น: username = admin , password = admin123")
