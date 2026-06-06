# คู่มือการนำเว็บขึ้นออนไลน์ (Deploy บน Render)

โปรเจกต์นี้พร้อม deploy แล้ว มีไฟล์ `render.yaml`, `Procfile`, `requirements.txt` ครบ  
ทำตามขั้นตอนด้านล่างเพื่อให้เว็บออนไลน์และมี URL ที่ใครก็เข้าได้

---

## ขั้นตอนที่ 1: สร้าง GitHub Repository

1. เปิด https://github.com แล้วเข้าสู่ระบบ (ถ้ายังไม่มีบัญชีให้สมัครก่อน ฟรี)
2. กดปุ่ม **New** (สีเขียว) มุมบนซ้าย
3. ตั้งชื่อ repository เช่น `police-duty-log`
4. เลือก **Public** (ถ้าเลือก Private ต้องอัปเกรด Render เป็นแบบเสียเงิน)
5. **อย่า**เลือก "Add a README file" หรือ .gitignore (เพราะเรามีไฟล์แล้ว)
6. กด **Create repository**
7. คัดลอก URL ที่ปรากฏ (รูปแบบ `https://github.com/username/police-duty-log.git`)

---

## ขั้นตอนที่ 2: Push โค้ดขึ้น GitHub

เปิด PowerShell ที่โฟลเดอร์ `PoliceDutyLog` แล้วรันคำสั่ง (แทน URL ด้วยของคุณจริง)

```powershell
cd C:\Users\Mixky\PoliceDutyLog
git remote add origin https://github.com/YOUR_USERNAME/police-duty-log.git
git branch -M main
git push -u origin main
```

> ถ้า GitHub ขอ username/password ให้ใช้ **Personal Access Token** แทนรหัสผ่าน  
> สร้างได้ที่ GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token  
> เลือก scope: `repo` (ทั้งหมด) แล้วคัดลอก token มาใช้แทนรหัสผ่าน

---

## ขั้นตอนที่ 3: Deploy บน Render

1. เปิด https://render.com แล้วเข้าสู่ระบบ (สมัครฟรีด้วยบัญชี GitHub ได้เลย)
2. กดปุ่ม **New +** มุมบนขวา เลือก **Blueprint**
3. เลือก repository `police-duty-log` ที่เพิ่ง push ขึ้น GitHub
4. Render จะอ่านไฟล์ `render.yaml` และแสดงว่าจะสร้าง
   - **Web Service** (police-duty-log) — เว็บแอป Flask
   - **PostgreSQL Database** (police-duty-db) — ฐานข้อมูล
5. กด **Apply** แล้วรอ build (~2-3 นาที)
6. เมื่อสถานะเป็น **Live** (สีเขียว) กดที่ชื่อ service แล้วคัดลอก URL

---

## ขั้นตอนที่ 4: ทดสอบเว็บ

เปิดเบราว์เซอร์ไปที่ URL ที่ Render ให้ (รูปแบบ `https://police-duty-log-xxxx.onrender.com`)

- เข้าสู่ระบบด้วย **admin** / **admin123**
- ทดสอบเพิ่มเจ้าหน้าที่ จัดเวร บันทึกเหตุการณ์
- แชร์ URL ให้เพื่อน อาจารย์ หรือกลุ่มเข้าใช้ได้ทันที

---

## หมายเหตุ

- **Render แผนฟรี** เว็บจะ sleep หลังไม่มีใครใช้ 15 นาที เปิดครั้งแรกหลัง sleep จะใช้เวลา ~30 วินาที
- **ฐานข้อมูล PostgreSQL ฟรี** เก็บได้ 1 GB (เพียงพอสำหรับงานนี้มาก)
- เวลา push โค้ดใหม่ขึ้น GitHub (git push) Render จะ build และ deploy ใหม่อัตโนมัติ
- URL ของเว็บไม่เปลี่ยน สามารถใช้ URL เดิมได้ตลอด

---

## คำถามที่พบบ่อย

**Build ล้มเหลว (Failed)?**
- เช็กว่า `requirements.txt` `Procfile` `render.yaml` มีครบและอยู่ในโฟลเดอร์เดียวกับ `app.py`
- ดู log ใน Render dashboard (กด Logs) เพื่อดูข้อผิดพลาด

**เข้าเว็บแล้วเจอข้อความ "Application Error"?**
- ให้รอ ~1 นาที (บางครั้ง PostgreSQL ยังไม่เสร็จ)
- ดู log ว่ามีข้อผิดพลาดอะไร

**อยากเปลี่ยนชื่อเว็บ?**
- ไปที่ Render dashboard → เลือก service → Settings → Name แก้ได้ (URL จะเปลี่ยนตาม)

---

ถ้ามีปัญหาหรือติดขั้นไหน ให้ส่งภาพหน้าจอหรือข้อความ error มาได้เลย
