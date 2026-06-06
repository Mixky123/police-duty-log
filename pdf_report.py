"""
สร้างรายงาน PDF สรุปเหตุการณ์รายเดือน
ใช้ reportlab สำหรับสร้าง PDF พร้อมรองรับ Unicode (ภาษาไทย)
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import io
import os


# ลงทะเบียนฟอนต์ไทย (ใช้ฟอนต์ที่มีใน Windows)
def register_thai_font():
    """ลงทะเบียนฟอนต์ไทยจากระบบ Windows"""
    try:
        # ใช้ Sarabun หรือ THSarabunNew ถ้ามีใน Windows
        font_path = "C:/Windows/Fonts/THSarabunNew.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('THFont', font_path))
            return 'THFont'

        # ถ้าไม่เจอ ใช้ Angsana
        font_path = "C:/Windows/Fonts/angsa.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('THFont', font_path))
            return 'THFont'

        # ถ้าไม่เจอเลย ใช้ Helvetica (ไม่รองรับไทย แต่ไม่ error)
        return 'Helvetica'
    except:
        return 'Helvetica'


def create_monthly_report_pdf(incidents, year, month, output_path=None):
    """
    สร้างไฟล์ PDF รายงานเหตุการณ์รายเดือน

    Args:
        incidents: list ของ dict เหตุการณ์
        year: ปี (int)
        month: เดือน (int)
        output_path: path ที่จะบันทึกไฟล์ (ถ้าไม่ระบุจะคืน BytesIO)

    Returns:
        BytesIO object หรือ None (ถ้าระบุ output_path)
    """
    # ลงทะเบียนฟอนต์ไทย
    thai_font = register_thai_font()

    # สร้าง buffer สำหรับ PDF
    if output_path:
        buffer = output_path
    else:
        buffer = io.BytesIO()

    # สร้าง PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           topMargin=2*cm, bottomMargin=2*cm,
                           leftMargin=2*cm, rightMargin=2*cm)

    # เตรียม styles
    styles = getSampleStyleSheet()

    # Style สำหรับหัวเรื่อง
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=thai_font,
        fontSize=18,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    # Style สำหรับหัวข้อย่อย
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=thai_font,
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=8,
    )

    # Style สำหรับข้อความปกติ
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=thai_font,
        fontSize=11,
        leading=14,
    )

    # เตรียม elements
    elements = []

    # หัวเรื่อง
    thai_months = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                   "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

    title_text = f"รายงานสรุปเหตุการณ์ประจำเดือน {thai_months[month]} {year + 543}"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.5*cm))

    # สรุปภาพรวม
    elements.append(Paragraph("สรุปภาพรวม", heading_style))

    total_incidents = len(incidents)
    by_category = {}
    by_severity = {}
    by_status = {}

    for inc in incidents:
        # นับตามประเภท
        cat = inc.get('category', 'ไม่ระบุ')
        by_category[cat] = by_category.get(cat, 0) + 1

        # นับตามความรุนแรง
        sev = inc.get('severity', 'ไม่ระบุ')
        by_severity[sev] = by_severity.get(sev, 0) + 1

        # นับตามสถานะ
        status = inc.get('status', 'ไม่ระบุ')
        by_status[status] = by_status.get(status, 0) + 1

    # ตารางสรุป
    summary_data = [
        ['ประเภทข้อมูล', 'จำนวน'],
        ['จำนวนเหตุการณ์ทั้งหมด', str(total_incidents)],
        ['', ''],
        ['แยกตามประเภท:', ''],
    ]

    for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
        summary_data.append([f'  {cat}', str(count)])

    summary_data.append(['', ''])
    summary_data.append(['แยกตามความรุนแรง:', ''])

    severity_order = ['วิกฤต', 'สูง', 'ปานกลาง', 'ต่ำ']
    for sev in severity_order:
        if sev in by_severity:
            summary_data.append([f'  {sev}', str(by_severity[sev])])

    summary_data.append(['', ''])
    summary_data.append(['แยกตามสถานะ:', ''])

    status_thai = {
        'pending': 'รอดำเนินการ',
        'investigating': 'กำลังสืบสวน',
        'resolved': 'แก้ไขแล้ว',
        'closed': 'ปิดงาน'
    }

    for status, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
        status_text = status_thai.get(status, status)
        summary_data.append([f'  {status_text}', str(count)])

    summary_table = Table(summary_data, colWidths=[12*cm, 3*cm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), thai_font),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), thai_font),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 1*cm))

    # รายละเอียดเหตุการณ์ทั้งหมด
    if incidents:
        elements.append(Paragraph("รายละเอียดเหตุการณ์", heading_style))
        elements.append(Spacer(1, 0.3*cm))

        # ตารางรายละเอียด
        detail_data = [['วันที่-เวลา', 'ประเภท', 'ความรุนแรง', 'สถานที่', 'เจ้าหน้าที่']]

        for inc in incidents:
            time_str = inc.get('incident_time', '')[:16]  # YYYY-MM-DD HH:MM
            category = inc.get('category', '')
            severity = inc.get('severity', '')
            location = inc.get('location', '')
            officer = inc.get('officer_name', '')
            if inc.get('rank'):
                officer = inc.get('rank') + ' ' + officer

            detail_data.append([
                time_str,
                category,
                severity,
                location[:20] + '...' if len(location) > 20 else location,
                officer[:15] + '...' if len(officer) > 15 else officer
            ])

        detail_table = Table(detail_data, colWidths=[3.5*cm, 3*cm, 2.5*cm, 4*cm, 4*cm])
        detail_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), thai_font),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), thai_font),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))

        elements.append(detail_table)

    # Footer
    elements.append(Spacer(1, 1*cm))
    footer_text = f"จัดทำโดย: ระบบจัดการเวรและบันทึกเหตุ | วันที่พิมพ์: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName=thai_font,
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(footer_text, footer_style))

    # สร้าง PDF
    doc.build(elements)

    if output_path:
        return None
    else:
        buffer.seek(0)
        return buffer


def test_pdf_generation():
    """ทดสอบสร้าง PDF"""
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

    test_incidents = [
        {
            'incident_time': '2026-06-01 08:30',
            'category': 'อุบัติเหตุจราจร',
            'severity': 'ปานกลาง',
            'location': 'สี่แยกกลางเมือง',
            'status': 'resolved',
            'officer_name': 'สมชาย ใจดี',
            'rank': 'ร.ต.ท.'
        },
        {
            'incident_time': '2026-06-02 14:15',
            'category': 'ลักทรัพย์',
            'severity': 'สูง',
            'location': 'ห้างสรรพสินค้า',
            'status': 'investigating',
            'officer_name': 'วิชัย กล้าหาญ',
            'rank': 'ร.ต.อ.'
        }
    ]

    output = create_monthly_report_pdf(test_incidents, 2026, 6, "test_report.pdf")
    print("PDF created successfully: test_report.pdf")


if __name__ == "__main__":
    test_pdf_generation()
