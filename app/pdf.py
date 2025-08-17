from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from io import BytesIO
from typing import List
from .models import Order, OrderItem, Payment
from datetime import datetime

def _header(c, title: str):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20*mm, 280*mm, title)
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, 274*mm, "Katil-Hospital.my | AA Alive Sdn Bhd (MDA-registered)")
    c.drawString(20*mm, 269*mm, "Tel/WhatsApp: +6011 2868 6592 | contact@evin2u.com")

def _label_value(c, x, y, label, value):
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, label)
    c.setFont("Helvetica", 10)
    c.drawString(x, y-12, value or "")

def invoice_pdf(order: Order) -> bytes:
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)

    _header(c, "INVOICE" if float(order.total) >= 0 else "CREDIT NOTE")

    _label_value(c, 20*mm, 255*mm, "Invoice No:", order.code)
    _label_value(c, 80*mm, 255*mm, "Date:", datetime.utcnow().strftime("%Y-%m-%d"))
    _label_value(c, 20*mm, 240*mm, "Bill To:", order.customer_name)
    _label_value(c, 20*mm, 228*mm, "Phone:", order.phone or "")
    _label_value(c, 20*mm, 216*mm, "Address:", (order.address or "")[:90])

    y = 200*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, y, "Item")
    c.drawString(120*mm, y, "Qty")
    c.drawString(140*mm, y, "Unit")
    c.drawString(165*mm, y, "Total")
    c.setFont("Helvetica", 10)
    y -= 8*mm
    for it in order.items:
        c.drawString(20*mm, y, f"{it.name} [{it.sku or '-'}]")
        c.drawRightString(135*mm, y, f"{float(it.qty):.0f}")
        c.drawRightString(160*mm, y, f"{float(it.unit_price):.2f}")
        c.drawRightString(190*mm, y, f"{float(it.line_total):.2f}")
        y -= 7*mm
        if y < 60*mm:
            c.showPage()
            y = 260*mm

    # Totals
    y -= 5*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(160*mm, y, "Subtotal:")
    c.drawRightString(190*mm, y, f"{float(order.subtotal):.2f}"); y -= 6*mm
    c.drawRightString(160*mm, y, "Discount:")
    c.drawRightString(190*mm, y, f"{float(order.discount):.2f}"); y -= 6*mm
    c.drawRightString(160*mm, y, "Delivery Fee:")
    c.drawRightString(190*mm, y, f"{float(order.delivery_fee):.2f}"); y -= 6*mm
    if float(order.return_delivery_fee) != 0:
        c.drawRightString(160*mm, y, "Return Delivery Fee:")
        c.drawRightString(190*mm, y, f"{float(order.return_delivery_fee):.2f}"); y -= 6*mm
    if float(order.penalty_amount) != 0:
        c.drawRightString(160*mm, y, "Penalty:")
        c.drawRightString(190*mm, y, f"{float(order.penalty_amount):.2f}"); y -= 6*mm
    if float(order.buyback_amount) != 0:
        c.drawRightString(160*mm, y, "Buyback:")
        c.drawRightString(190*mm, y, f"{float(order.buyback_amount):.2f}"); y -= 6*mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(160*mm, y, "TOTAL:")
    c.drawRightString(190*mm, y, f"{float(order.total):.2f}")

    c.showPage()
    c.save()
    return bio.getvalue()

def receipt_pdf(order: Order, payment: Payment) -> bytes:
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    _header(c, "RECEIPT")
    _label_value(c, 20*mm, 255*mm, "Receipt For Invoice:", order.code)
    _label_value(c, 80*mm, 255*mm, "Receipt Date:", payment.created_at.strftime("%Y-%m-%d"))
    _label_value(c, 20*mm, 240*mm, "Customer:", order.customer_name)
    _label_value(c, 20*mm, 228*mm, "Method:", str(payment.method))
    _label_value(c, 20*mm, 216*mm, "Reference:", payment.reference or "-")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(190*mm, 200*mm, f"RECEIVED: {float(payment.amount):.2f}")
    c.showPage(); c.save()
    return bio.getvalue()

def instalment_agreement_pdf(order: Order) -> bytes:
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    _header(c, "INSTALMENT AGREEMENT")
    c.setFont("Helvetica", 11)
    y = 250*mm
    lines = [
        f"Customer: {order.customer_name}  Phone: {order.phone or '-'}",
        f"Address: {order.address or '-'}",
        f"Agreement No: {order.code}",
        f"Tenure: {order.instalment_months_total} months  Monthly: {float(order.instalment_monthly_amount):.2f}",
        "No proration. Payments due monthly from start date. Late/failed payments may incur penalties.",
        "If customer cancels instalment early, a penalty may be charged and return delivery fee applies.",
        "Company is MDA-registered (AA Alive Sdn Bhd) and provides hospital beds, wheelchairs, and oxygen concentrators.",
    ]
    for ln in lines:
        c.drawString(20*mm, y, ln); y -= 8*mm
    c.showPage(); c.save()
    return bio.getvalue()
