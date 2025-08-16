from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def invoice_pdf_bytes(order) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Invoice_{order.order_code}")
    pdf.drawString(100, 800, f"Invoice for Order {order.order_code}")
    pdf.drawString(100, 780, f"Customer: {order.customer.name if order.customer else ''}")
    y = 760
    for item in order.items:
        pdf.drawString(120, y, f"{item.qty} x {item.name} @ {float(item.unit_price):.2f}")
        y -= 20
    initial = sum(float(l.amount) for l in order.ledger if l.kind.name == "INITIAL_CHARGE")
    monthly = sum(float(l.amount) for l in order.ledger if l.kind.name == "MONTHLY_CHARGE")
    paid = sum(float(p.amount) for p in order.payments)
    outstanding = initial + monthly - paid
    pdf.drawString(100, y-20, f"Outstanding Balance: {outstanding:.2f}")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()

def receipt_pdf_bytes(order, amount: float) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Receipt_{order.order_code}")
    pdf.drawString(100, 800, f"Receipt for Order {order.order_code}")
    pdf.drawString(100, 780, f"Received Amount: {amount:.2f}")
    pdf.drawString(100, 760, f"Customer: {order.customer.name if order.customer else ''}")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
