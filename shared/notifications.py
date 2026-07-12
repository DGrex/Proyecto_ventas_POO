import io
import requests
from django.conf import settings
from django.core.mail import EmailMessage
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)


def generate_invoice_pdf(invoice):
    """
    Genera el comprobante de una factura en PDF y devuelve los bytes.
    Reutilizable tanto para mostrarlo en el modal como para adjuntarlo al correo.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'InvoiceTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=18,
        textColor=colors.HexColor('#1d4ed8'), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'InvoiceSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9,
        textColor=colors.HexColor('#6b7280'), spaceAfter=14
    )
    label_style = ParagraphStyle(
        'InvoiceLabel', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9,
        textColor=colors.HexColor('#374151')
    )

    elements = []

    # ── Encabezado ─────────────────────────────────────
    elements.append(Paragraph('TecnoStock S.A.', title_style))
    elements.append(Paragraph('Comprobante de Venta', subtitle_style))

    info_data = [
        [Paragraph('<b>Factura Nº:</b>', label_style), f'#{invoice.id}',
         Paragraph('<b>Fecha:</b>', label_style), invoice.invoice_date.strftime('%d/%m/%Y %H:%M')],
        [Paragraph('<b>Cliente:</b>', label_style), invoice.customer.full_name,
         Paragraph('<b>DNI/RUC:</b>', label_style), invoice.customer.dni],
        [Paragraph('<b>Tipo de Pago:</b>', label_style), invoice.get_tipo_pago_display(),
         Paragraph('<b>Estado:</b>', label_style), invoice.get_estado_display()],
    ]
    info_table = Table(info_data, colWidths=[80, 170, 80, 170])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 16))

    # ── Detalle de productos ───────────────────────────
    header = ['Producto', 'Cantidad', 'Precio Unit.', 'Subtotal']
    rows = [header]
    for d in invoice.details.all():
        rows.append([
            d.product.name,
            str(d.quantity),
            f'${d.unit_price}',
            f'${d.subtotal}',
        ])

    detail_table = Table(rows, colWidths=[220, 80, 100, 100])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 16))

    # ── Totales ─────────────────────────────────────────
    totals_data = [
        ['Subtotal:', f'${invoice.subtotal}'],
        ['IVA (15%):', f'${invoice.tax}'],
        ['TOTAL:', f'${invoice.total}'],
    ]
    if invoice.tipo_pago == 'credito':
        totals_data.append(['Saldo Pendiente:', f'${invoice.saldo}'])

    totals_table = Table(totals_data, colWidths=[420, 100])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1d4ed8')),
        ('TOPPADDING', (0, -1), (-1, -1), 6),
    ]))
    elements.append(totals_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def send_invoice_email(invoice, pdf_bytes):
    """Envía el comprobante de la factura por correo al cliente, si tiene email registrado."""
    if not invoice.customer.email:
        return False, 'El cliente no tiene correo electrónico registrado.'

    subject = f'TecnoStock - Factura #{invoice.id}'
    body = (
        f'Hola {invoice.customer.first_name},\n\n'
        f'Adjuntamos el comprobante de tu compra #{invoice.id} por un total de ${invoice.total}.\n\n'
        f'Gracias por tu preferencia.\n\nTecnoStock S.A.'
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer.email],
    )
    email.attach(f'factura_{invoice.id}.pdf', pdf_bytes, 'application/pdf')

    try:
        email.send(fail_silently=False)
        return True, 'Correo enviado correctamente.'
    except Exception as e:
        return False, f'Error al enviar correo: {e}'

def send_invoice_whatsapp(invoice):
    """
    Envía un resumen de la factura por WhatsApp usando CallMeBot.
    Usa la API key propia del cliente (cada cliente se suscribe con su propio número).
    """
    customer = invoice.customer

    if not customer.phone:
        return False, 'El cliente no tiene teléfono registrado.'
    if not customer.whatsapp_apikey:
        return False, 'El cliente no tiene una API key de WhatsApp configurada (no está suscrito a CallMeBot).'

    phone = customer.phone.replace(' ', '').replace('-', '')
    message = (
        f'🧾 *TecnoStock* - Factura #{invoice.id}\n'
        f'Cliente: {customer.full_name}\n'
        f'Total: ${invoice.total}\n'
        f'Estado: {invoice.get_estado_display()}\n'
        f'¡Gracias por tu compra!'
    )

    url = 'https://api.callmebot.com/whatsapp.php'
    params = {
        'phone': phone,
        'text': message,
        'apikey': customer.whatsapp_apikey,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True, 'Mensaje de WhatsApp enviado correctamente.'
        return False, f'CallMeBot respondió con estado {response.status_code}: {response.text}'
    except Exception as e:
        return False, f'Error al enviar WhatsApp: {e}'