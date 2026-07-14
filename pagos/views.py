from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from purchasing.models import Purchase
from shared.decorators import audit_action, group_required
from shared.notifications import generate_pago_receipt_pdf, send_pago_receipt_email
from .models import PagoCompra
from .forms import PagoCompraForm


@login_required
@group_required('Administrador', 'Analista de Compras')
@permission_required('purchasing.view_purchase', raise_exception=True)
@audit_action('LIST_COMPRAS_PENDIENTES')
def compra_pendiente_list(request):
    """Lista las compras a crédito. Por defecto muestra solo PENDIENTE, con filtro de estado."""
    compras = Purchase.objects.filter(tipo_pago='credito').select_related('supplier')

    estado = request.GET.get('estado', 'PENDIENTE')
    if estado and estado != 'TODOS':
        compras = compras.filter(estado=estado)

    doc_number = request.GET.get('doc_number')
    if doc_number:
        compras = compras.filter(document_number__icontains=doc_number)

    paginator = Paginator(compras, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'pagos/compra_pendiente_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'compras': page_obj,
        'estado_filter': estado,
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@permission_required('pagos.add_pagocompra', raise_exception=True)
@audit_action('CREATE_PAGO')
def pago_create(request, compra_id):
    """Registra un abono sobre una compra a crédito."""
    compra = get_object_or_404(Purchase, pk=compra_id)

    if compra.estado == 'ANULADA':
        messages.error(request, 'No se puede pagar una compra anulada.')
        return redirect('pagos:compra_pendiente_list')

    if request.method == 'POST':
        form = PagoCompraForm(request.POST, compra=compra)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.compra = compra
            pago.save()

            # ── Comprobante interno + aviso de pago al proveedor (mejor esfuerzo) ──
            pdf_bytes = generate_pago_receipt_pdf(pago)
            ok_email, msg_email = send_pago_receipt_email(pago, pdf_bytes)
            if ok_email:
                messages.info(request, '📧 Aviso de pago enviado al correo del proveedor.')
            else:
                messages.warning(request, f'No se pudo enviar el correo al proveedor: {msg_email}')

            messages.success(request, f'Abono de ${pago.valor} registrado correctamente!')
            return redirect(f"{reverse('pagos:pago_list', kwargs={'compra_id': compra.id})}?voucher={pago.pk}")
    else:
        form = PagoCompraForm(compra=compra)

    return render(request, 'pagos/pago_form.html', {
        'form': form,
        'compra': compra,
        'title': f'Registrar Pago - Compra #{compra.id}',
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@permission_required('pagos.view_pagocompra', raise_exception=True)
@audit_action('LIST_PAGOS')
def pago_list(request, compra_id):
    """Historial de pagos de una compra."""
    compra = get_object_or_404(Purchase, pk=compra_id)
    pagos = PagoCompra.objects.filter(compra=compra)

    paginator = Paginator(pagos, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'pagos/pago_list.html', {
        'compra': compra,
        'page_obj': page_obj,
        'paginator': paginator,
        'pagos': page_obj,
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@permission_required('pagos.change_pagocompra', raise_exception=True)
@audit_action('UPDATE_PAGO')
def pago_update(request, pk):
    """Edita un abono existente."""
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra = pago.compra

    if request.method == 'POST':
        form = PagoCompraForm(request.POST, instance=pago, compra=compra)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pago actualizado correctamente!')
            return redirect('pagos:pago_list', compra_id=compra.id)
    else:
        form = PagoCompraForm(instance=pago, compra=compra)

    return render(request, 'pagos/pago_form.html', {
        'form': form,
        'compra': compra,
        'title': 'Editar Pago',
    })


@login_required
@group_required('Administrador')
@permission_required('pagos.delete_pagocompra', raise_exception=True)
@audit_action('DELETE_PAGO')
def pago_delete(request, pk):
    """Elimina un abono (solo si la compra no está ya cancelada)."""
    pago = get_object_or_404(PagoCompra, pk=pk)
    compra_id = pago.compra_id

    if pago.compra.estado == 'PAGADA':
        messages.error(
            request,
            'No se puede eliminar un pago de una compra ya cancelada '
            '(edite el pago en vez de eliminarlo, o contacte a contabilidad).'
        )
        return redirect('pagos:pago_list', compra_id=compra_id)

    if request.method == 'POST':
        valor = pago.valor
        pago.delete()
        messages.success(request, f'Pago de ${valor} eliminado correctamente!')
        return redirect('pagos:pago_list', compra_id=compra_id)

    return render(request, 'pagos/pago_confirm_delete.html', {'object': pago})

@login_required
@permission_required('pagos.view_pagocompra', raise_exception=True)
@xframe_options_sameorigin
def pago_comprobante_pdf(request, pk):
    """Sirve el comprobante/aviso de pago a proveedor en PDF, embebido (inline) para el modal."""
    pago = get_object_or_404(
        PagoCompra.objects.select_related('compra__supplier'), pk=pk
    )
    pdf_bytes = generate_pago_receipt_pdf(pago)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="comprobante_pago_{pago.id}.pdf"'
    return response
