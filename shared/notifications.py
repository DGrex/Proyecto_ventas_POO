import io
import requests
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum
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

# ══════════════════════════════════════════════════════════════════
# COMPROBANTE DE ABONO (COBROS - pagos que hace un cliente)
# ══════════════════════════════════════════════════════════════════

def generate_cobro_receipt_pdf(cobro):
    """
    Genera el comprobante de un abono de cliente sobre una factura a crédito.
    Muestra: valor abonado, total abonado acumulado y saldo restante.
    """
    factura = cobro.factura
    total_abonado = factura.cobros.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ReceiptTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=18,
        textColor=colors.HexColor('#047857'), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'ReceiptSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9,
        textColor=colors.HexColor('#6b7280'), spaceAfter=14
    )
    label_style = ParagraphStyle(
        'ReceiptLabel', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9,
        textColor=colors.HexColor('#374151')
    )

    elements = []
    elements.append(Paragraph('TecnoStock S.A.', title_style))
    elements.append(Paragraph('Comprobante de Abono a Factura', subtitle_style))

    info_data = [
        [Paragraph('<b>Recibo Nº:</b>', label_style), f'#{cobro.id}',
         Paragraph('<b>Fecha del Abono:</b>', label_style), cobro.fecha.strftime('%d/%m/%Y')],
        [Paragraph('<b>Cliente:</b>', label_style), factura.customer.full_name,
         Paragraph('<b>Factura Nº:</b>', label_style), f'#{factura.id}'],
    ]
    info_table = Table(info_data, colWidths=[90, 160, 90, 160])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 18))

# en generate_cobro_receipt_pdf
    resumen_data = [
        ['Total de la Factura:', f'${factura.total:.2f}'],
        ['Valor Abonado (este pago):', f'${cobro.valor:.2f}'],
        ['Total Abonado Acumulado:', f'${total_abonado:.2f}'],
        ['Saldo Pendiente:', f'${factura.saldo:.2f}'],
    ]
    resumen_table = Table(resumen_data, colWidths=[340, 120])
    resumen_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#047857')),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#b91c1c') if factura.saldo > 0 else colors.HexColor('#047857')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#374151')),
    ]))
    elements.append(resumen_table)
    elements.append(Spacer(1, 24))

    estado_txt = 'FACTURA CANCELADA EN SU TOTALIDAD' if factura.saldo == Decimal('0') else 'FACTURA CON SALDO PENDIENTE'
    elements.append(Paragraph(f'<b>Estado:</b> {estado_txt}', label_style))

    if cobro.observacion:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<b>Observación:</b> {cobro.observacion}', label_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def send_cobro_receipt_email(cobro, pdf_bytes):
    """Envía el comprobante de abono al correo del cliente."""
    factura = cobro.factura
    customer = factura.customer

    if not customer.email:
        return False, 'El cliente no tiene correo electrónico registrado.'

    subject = f'TecnoStock - Comprobante de Abono (Factura #{factura.id})'
    body = (
        f'Hola {customer.first_name},\n\n'
        f'Confirmamos la recepción de tu abono de ${cobro.valor} sobre la factura #{factura.id}.\n'
        f'Saldo pendiente actual: ${factura.saldo}.\n\n'
        f'Adjuntamos el comprobante correspondiente.\n\nGracias por tu preferencia.\nTecnoStock S.A.'
    )
    email = EmailMessage(
        subject=subject, body=body,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[customer.email],
    )
    email.attach(f'comprobante_abono_{cobro.id}.pdf', pdf_bytes, 'application/pdf')

    try:
        email.send(fail_silently=False)
        return True, 'Correo enviado correctamente.'
    except Exception as e:
        return False, f'Error al enviar correo: {e}'


def send_cobro_whatsapp(cobro):
    """Envía confirmación de abono por WhatsApp usando la API key propia del cliente."""
    factura = cobro.factura
    customer = factura.customer

    if not customer.phone:
        return False, 'El cliente no tiene teléfono registrado.'
    if not customer.whatsapp_apikey:
        return False, 'El cliente no tiene una API key de WhatsApp configurada.'

    phone = customer.phone.replace(' ', '').replace('-', '')
    message = (
        f'💰 *TecnoStock* - Abono Registrado\n'
        f'Factura #{factura.id}\n'
        f'Abono recibido: ${cobro.valor}\n'
        f'Saldo pendiente: ${factura.saldo}\n'
        f'¡Gracias por tu pago!'
    )
    url = 'https://api.callmebot.com/whatsapp.php'
    params = {'phone': phone, 'text': message, 'apikey': customer.whatsapp_apikey}

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True, 'Mensaje de WhatsApp enviado correctamente.'
        return False, f'CallMeBot respondió con estado {response.status_code}: {response.text}'
    except Exception as e:
        return False, f'Error al enviar WhatsApp: {e}'


# ══════════════════════════════════════════════════════════════════
# COMPROBANTE DE PAGO A PROVEEDOR (PAGOS - pagos que tú haces)
# ══════════════════════════════════════════════════════════════════

def generate_pago_receipt_pdf(pago):
    """
    Genera el comprobante interno (aviso de pago / remittance advice) de un
    pago realizado a un proveedor sobre una compra a crédito.
    """
    compra = pago.compra
    total_pagado = compra.pagos.aggregate(total=Sum('valor'))['total'] or Decimal('0')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'PagoTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=18,
        textColor=colors.HexColor('#1d4ed8'), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'PagoSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9,
        textColor=colors.HexColor('#6b7280'), spaceAfter=14
    )
    label_style = ParagraphStyle(
        'PagoLabel', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9,
        textColor=colors.HexColor('#374151')
    )

    elements = []
    elements.append(Paragraph('TecnoStock S.A.', title_style))
    elements.append(Paragraph('Comprobante / Aviso de Pago a Proveedor', subtitle_style))

    info_data = [
        [Paragraph('<b>Comprobante Nº:</b>', label_style), f'#{pago.id}',
         Paragraph('<b>Fecha de Pago:</b>', label_style), pago.fecha.strftime('%d/%m/%Y')],
        [Paragraph('<b>Proveedor:</b>', label_style), compra.supplier.name,
         Paragraph('<b>Nº Factura Proveedor:</b>', label_style), compra.document_number],
        [Paragraph('<b>Compra Interna Nº:</b>', label_style), f'#{compra.id}', '', ''],
    ]
    info_table = Table(info_data, colWidths=[90, 160, 100, 150])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 18))

# en generate_pago_receipt_pdf
    resumen_data = [
        ['Total de la Compra:', f'${compra.total:.2f}'],
        ['Valor Pagado (este pago):', f'${pago.valor:.2f}'],
        ['Total Pagado Acumulado:', f'${total_pagado:.2f}'],
        ['Saldo Pendiente con el Proveedor:', f'${compra.saldo:.2f}'],
    ]
    resumen_table = Table(resumen_data, colWidths=[340, 120])
    resumen_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#1d4ed8')),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#b91c1c') if compra.saldo > 0 else colors.HexColor('#047857')),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#374151')),
    ]))
    elements.append(resumen_table)
    elements.append(Spacer(1, 24))

    estado_txt = 'COMPRA CANCELADA EN SU TOTALIDAD' if compra.saldo == Decimal('0') else 'COMPRA CON SALDO PENDIENTE'
    elements.append(Paragraph(f'<b>Estado:</b> {estado_txt}', label_style))

    if pago.observacion:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f'<b>Observación:</b> {pago.observacion}', label_style))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        '<i>Este comprobante es un aviso interno de pago (remittance advice), '
        'útil para que el proveedor concilie sus cuentas.</i>',
        subtitle_style
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def send_pago_receipt_email(pago, pdf_bytes):
    """
    Envía el comprobante de pago al correo del proveedor, como cortesía profesional
    para que puedan conciliar que su factura fue cancelada.
    """
    compra = pago.compra
    supplier = compra.supplier

    if not supplier.email:
        return False, 'El proveedor no tiene correo electrónico registrado.'

    subject = f'TecnoStock - Aviso de Pago (Compra #{compra.id} / Factura {compra.document_number})'
    body = (
        f'Estimados {supplier.name},\n\n'
        f'Les confirmamos que hemos realizado un pago de ${pago.valor} correspondiente '
        f'a la factura {compra.document_number} (nuestra referencia interna: Compra #{compra.id}).\n'
        f'Saldo pendiente actual con nosotros: ${compra.saldo}.\n\n'
        f'Adjuntamos el comprobante de pago para su conciliación contable.\n\n'
        f'Saludos cordiales,\nTecnoStock S.A.'
    )
    email = EmailMessage(
        subject=subject, body=body,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[supplier.email],
    )
    email.attach(f'comprobante_pago_{pago.id}.pdf', pdf_bytes, 'application/pdf')

    try:
        email.send(fail_silently=False)
        return True, 'Correo enviado al proveedor correctamente.'
    except Exception as e:
        return False, f'Error al enviar correo: {e}'


def send_user_activation_email(user, activation_url):
    """
    Envía al correo del usuario recién creado un enlace seguro y de un
    solo uso para que él mismo defina su contraseña (no se envía ninguna
    contraseña en texto plano). El enlace usa el mismo mecanismo de token
    que "olvidé mi contraseña" de Django, por lo que expira y deja de
    servir en cuanto se usa.
    """
    if not user.email:
        return False, 'El usuario no tiene un correo electrónico registrado.'

    subject = 'TecnoStock - Activa tu cuenta'
    body = (
        f'Hola {user.first_name or user.username},\n\n'
        f'Se ha creado una cuenta para ti en el sistema TecnoStock.\n'
        f'Usuario: {user.username}\n\n'
        f'Para activar tu cuenta y crear tu propia contraseña, ingresa al siguiente enlace:\n'
        f'{activation_url}\n\n'
        f'Este enlace es personal, de un solo uso, y dejará de funcionar una vez que '
        f'definas tu contraseña.\n\n'
        f'Saludos,\nTecnoStock S.A.'
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )

    try:
        email.send(fail_silently=False)
        return True, 'Enlace de activación enviado por correo correctamente.'
    except Exception as e:
        return False, f'No se pudo enviar el correo de activación: {e}'


# ══════════════════════════════════════════════════════════════════
# AUTENTICACIÓN DE DOS PASOS (2FA) POR CORREO
# ══════════════════════════════════════════════════════════════════

def send_2fa_code_email(user, codigo):
    """Envía el código de verificación de 2 pasos al correo del usuario."""
    if not user.email:
        return False, 'El usuario no tiene un correo registrado.'

    subject = 'TecnoStock - Código de verificación de acceso'
    body = (
        f'Hola {user.first_name or user.username},\n\n'
        f'Tu código de verificación para iniciar sesión es:\n\n'
        f'    {codigo}\n\n'
        f'Este código expira en 10 minutos. Si tú no intentaste iniciar sesión, '
        f'ignora este mensaje y considera cambiar tu contraseña.\n\n'
        f'TecnoStock S.A.'
    )
    email = EmailMessage(
        subject=subject, body=body,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email],
    )
    try:
        email.send(fail_silently=False)
        return True, 'Código enviado correctamente.'
    except Exception as e:
        return False, f'Error al enviar el código: {e}'
