from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from purchasing.models import Purchase
from shared.decorators import audit_action, group_required
from .models import PagoCompra
from .forms import PagoCompraForm


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('LIST_COMPRAS_PENDIENTES')
def compra_pendiente_list(request):
    """Lista únicamente las compras a crédito con saldo pendiente."""
    compras = Purchase.objects.filter(
        tipo_pago='credito',
        estado='PENDIENTE',
    ).select_related('supplier')

    doc_number = request.GET.get('doc_number')
    if doc_number:
        compras = compras.filter(document_number__icontains=doc_number)

    paginator = Paginator(compras, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'pagos/compra_pendiente_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'compras': page_obj,
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
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
            messages.success(request, f'Abono de ${pago.valor} registrado correctamente!')
            return redirect('pagos:pago_list', compra_id=compra.id)
    else:
        form = PagoCompraForm(compra=compra)

    return render(request, 'pagos/pago_form.html', {
        'form': form,
        'compra': compra,
        'title': f'Registrar Pago - Compra #{compra.id}',
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
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