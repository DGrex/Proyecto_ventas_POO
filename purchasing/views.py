import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Q
from .models import Purchase, PurchaseDetail
from .forms import PurchaseForm, PurchaseDetailFormSet
from billing.models import Product, Supplier
from shared.decorators import audit_action, group_required
from shared.mixins import ExportMixin
 

class PurchaseExportHelper(ExportMixin):
    model = Purchase
    export_filename = 'compras'
    export_fields = [
        ('id', 'ID'),
        ('supplier.name', 'Proveedor'),
        ('document_number', 'Nº Factura Proveedor'),
        ('purchase_date', 'Fecha Compra'),
        ('subtotal', 'Subtotal'),
        ('tax', 'Impuesto'),
        ('total', 'Total'),
    ]

@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('LIST_PURCHASES')
def purchase_list(request):
    """Lista todas las compras realizadas a proveedores con filtros."""
    purchases = Purchase.objects.all().select_related('supplier')
    
    # Reto 3: Filtros de búsqueda (proveedor y rango de fechas)
    p = request.GET
    supplier_id = p.get('supplier', '')
    date_min = p.get('date_min', '')
    date_max = p.get('date_max', '')
    doc_number = p.get('doc_number', '')

    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)
    if doc_number:
        purchases = purchases.filter(document_number__icontains=doc_number)
    if date_min and date_max:
        purchases = purchases.filter(purchase_date__date__range=[date_min, date_max])
    elif date_min:
        purchases = purchases.filter(purchase_date__date__gte=date_min)
    elif date_max:
        purchases = purchases.filter(purchase_date__date__lte=date_max)

    export_format = p.get('export')
    if export_format in ['excel', 'pdf']:
        helper = PurchaseExportHelper()
        helper.request = request
        fields = helper.get_export_fields()
        filename = helper.get_export_filename()
        if export_format == 'excel':
            return helper.export_to_excel(purchases, fields, filename)
        return helper.export_to_pdf(purchases, fields, filename)

    # Reto 4: Reporte - Costo promedio general por producto comprado
    avg_cost_data = PurchaseDetail.objects.aggregate(avg_cost=Avg('unit_cost'))
    avg_cost = avg_cost_data['avg_cost'] or Decimal('0.00')

    # Paginación
    paginator = Paginator(purchases, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Catálogo de proveedores activos para el selector de filtros
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')

    # Construir query string para paginación
    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    has_active_filters = any([supplier_id, date_min, date_max, doc_number])

    ALL_COLUMNS = [
        ('id', 'ID'),
        ('supplier', 'Proveedor'),
        ('document_number', 'Nº Factura Proveedor'),
        ('purchase_date', 'Fecha Compra'),
        ('subtotal', 'Subtotal'),
        ('tax', 'Impuesto'),
        ('total', 'Total'),
    ]
    columns = request.GET.getlist('columns')
    if not columns:
        columns = [c[0] for c in ALL_COLUMNS]

    return render(request, 'purchasing/purchase_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'avg_cost': avg_cost,
        'suppliers': suppliers,
        'filter': p,
        'query_string': query_string,
        'has_active_filters': has_active_filters,
        'available_columns': ALL_COLUMNS,
        'selected_columns': columns,
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('CREATE_PURCHASE')
def purchase_create(request):
    """Crea una nueva compra y actualiza el stock."""
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        formset = PurchaseDetailFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardamos cabecera
                    purchase = form.save(commit=False)
                    purchase.save()

                    # Guardamos detalles (este save() aumenta el stock de cada producto en la BD)
                    formset.instance = purchase
                    formset.save()

                    # Calculamos los totales finales de la cabecera de compra
                    subtotal = sum(d.subtotal for d in purchase.details.all())
                    purchase.subtotal = subtotal
                    purchase.tax = subtotal * Decimal('0.15')  # IVA 15%
                    purchase.total = purchase.subtotal + purchase.tax
                    purchase.save()

                messages.success(request, f'Compra #{purchase.id} registrada exitosamente! Total: ${purchase.total}')
                return redirect('purchasing:purchase_list')
            except Exception as e:
                form.add_error(None, f"Error al guardar la compra: {str(e)}")
    else:
        form = PurchaseForm()
        formset = PurchaseDetailFormSet()

    # Serializar productos activos con su stock y precio de venta actual (para referencia del costo)
    products_qs = Product.objects.filter(is_active=True).select_related('brand')
    products_data = [
        {
            'id': p.id,
            'name': f"{p.name} ({p.brand.name})",
            'unit_price': float(p.unit_price),  # Precio de venta referencial
            'stock': p.stock
        }
        for p in products_qs
    ]
    products_json = json.dumps(products_data, cls=DjangoJSONEncoder)

    return render(request, 'purchasing/purchase_form.html', {
        'form': form,
        'formset': formset,
        'products_json': products_json,
        'title': 'Registrar Compra',
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('UPDATE_PURCHASE')
def purchase_update(request, pk):
    """Modifica una compra existente y ajusta el stock."""
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        form = PurchaseForm(request.POST, instance=purchase)
        formset = PurchaseDetailFormSet(request.POST, instance=purchase)

        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardamos la cabecera
                    purchase = form.save()

                    # Guardamos detalles (este save() ajusta las diferencias de stock en la BD)
                    formset.save()

                    # Recalculamos los totales de la compra
                    subtotal = sum(d.subtotal for d in purchase.details.all())
                    purchase.subtotal = subtotal
                    purchase.tax = subtotal * Decimal('0.15')  # IVA 15%
                    purchase.total = purchase.subtotal + purchase.tax
                    purchase.save()

                messages.success(request, f'Compra #{purchase.id} actualizada correctamente! Total: ${purchase.total}')
                return redirect('purchasing:purchase_list')
            except Exception as e:
                form.add_error(None, f"Error al guardar la compra: {str(e)}")
    else:
        form = PurchaseForm(instance=purchase)
        formset = PurchaseDetailFormSet(instance=purchase)

    # Serializar productos activos
    products_qs = Product.objects.filter(is_active=True).select_related('brand')
    products_data = [
        {
            'id': p.id,
            'name': f"{p.name} ({p.brand.name})",
            'unit_price': float(p.unit_price),
            'stock': p.stock
        }
        for p in products_qs
    ]
    # Incluir productos inactivos si están ya en el detalle de esta compra
    existing_product_ids = set(purchase.details.values_list('product_id', flat=True))
    active_product_ids = set(p['id'] for p in products_data)
    missing_ids = existing_product_ids - active_product_ids
    if missing_ids:
        missing_products = Product.objects.filter(id__in=missing_ids).select_related('brand')
        for p in missing_products:
            products_data.append({
                'id': p.id,
                'name': f"{p.name} ({p.brand.name}) [Inactivo]",
                'unit_price': float(p.unit_price),
                'stock': p.stock
            })

    products_json = json.dumps(products_data, cls=DjangoJSONEncoder)

    return render(request, 'purchasing/purchase_form.html', {
        'form': form,
        'formset': formset,
        'products_json': products_json,
        'title': 'Editar Compra',
    })


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('DETAIL_PURCHASE')
def purchase_detail(request, pk):
    """Muestra el detalle completo de una compra."""
    purchase = get_object_or_404(
        Purchase.objects.select_related('supplier').prefetch_related('details__product'),
        pk=pk
    )
    return render(request, 'purchasing/purchase_detail.html', {'purchase': purchase})


@login_required
@group_required('Administrador')
@audit_action('DELETE_PURCHASE')
def purchase_delete(request, pk):
    """Elimina una compra y todos sus detalles (CASCADE), devolviendo el stock."""
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == 'POST':
        purchase_id = purchase.id
        # La eliminación en cascada disparará la señal post_delete para cada línea de detalle,
        # lo que restará las cantidades correspondientes del inventario automáticamente.
        purchase.delete()
        messages.success(request, f'Compra #{purchase_id} eliminada correctamente!')
        return redirect('purchasing:purchase_list')
    return render(request, 'purchasing/purchase_confirm_delete.html', {'object': purchase})
