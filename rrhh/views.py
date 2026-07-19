from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from shared.mixins import ExportMixin, check_export_permission

from .forms import PrestamoForm
from .models import Empleado, Prestamo, PrestamoDetalle, TipoPrestamo


class PrestamoExportHelper(ExportMixin):
    model = Prestamo
    export_filename = 'prestamos'
    export_fields = [
        ('id', 'ID'),
        ('empleado.nombres', 'Empleado'),
        ('tipo_prestamo.descripcion', 'Tipo de préstamo'),
        ('fecha_prestamo', 'Fecha'),
        ('monto', 'Monto'),
        ('interes', 'Interés'),
        ('monto_pagar', 'Total a pagar'),
        ('numero_cuotas', 'Cuotas'),
        ('saldo', 'Saldo'),
        ('estado', 'Estado'),
    ]


@login_required
@permission_required('rrhh.view_prestamo', raise_exception=True)
def prestamo_list(request):


    prestamos = Prestamo.objects.select_related("empleado", "tipo_prestamo").order_by("-id")

    p = request.GET
    empleado_id = p.get("empleado", "")
    tipo_prestamo_id = p.get("tipo_prestamo", "")
    estado = p.get("estado", "")
    fecha_min = p.get("fecha_min", "")
    fecha_max = p.get("fecha_max", "")

    if empleado_id:
        prestamos = prestamos.filter(empleado_id=empleado_id)
    if tipo_prestamo_id:
        prestamos = prestamos.filter(tipo_prestamo_id=tipo_prestamo_id)
    if estado:
        prestamos = prestamos.filter(estado=estado)
    if fecha_min:
        prestamos = prestamos.filter(fecha_prestamo__gte=fecha_min)
    if fecha_max:
        prestamos = prestamos.filter(fecha_prestamo__lte=fecha_max)

    export_format = p.get('export')
    if export_format in ['excel', 'pdf']:
        redirect_response = check_export_permission(request, export_format)
        if redirect_response:
            return redirect_response

        helper = PrestamoExportHelper()
        helper.request = request
        fields = helper.get_export_fields()
        filename = helper.get_export_filename()

        if export_format == 'excel':
            return helper.export_to_excel(prestamos, fields, filename)
        return helper.export_to_pdf(prestamos, fields, filename)

    params = p.copy()
    params.pop("page", None)
    query_string = params.urlencode()

    has_active_filters = any([empleado_id, tipo_prestamo_id, estado, fecha_min, fecha_max])

    context = {
        "prestamos": prestamos,
        "empleados_catalog": Empleado.objects.order_by("nombres"),
        "tipos_prestamo_catalog": TipoPrestamo.objects.order_by("descripcion"),
        "estados_catalog": Prestamo.ESTADOS,
        "filter": p,
        "query_string": query_string,
        "has_active_filters": has_active_filters,
    }

    return render(request, "rrhh/prestamo_list.html", context)


@login_required
@permission_required('rrhh.add_prestamo', raise_exception=True)
def prestamo_create(request):
  

    if request.method == "POST":
        form = PrestamoForm(request.POST)

        if form.is_valid():
            prestamo = form.save(commit=False)
            prestamo.fecha_prestamo = timezone.localdate()
            prestamo.generar_prestamo()

            messages.success(request, f"Préstamo #{prestamo.id} registrado correctamente.")
            return redirect("rrhh:prestamo_detail", pk=prestamo.pk)
    else:
        form = PrestamoForm()

    tasas_prestamo = {str(t.id): float(t.tasa_interes) for t in TipoPrestamo.objects.all()}

    return render(
        request,
        "rrhh/prestamo_form.html",
        {"form": form, "title": "Nuevo Préstamo", "tasas_prestamo": tasas_prestamo},
    )


@login_required
@permission_required('rrhh.change_prestamo', raise_exception=True)
def prestamo_update(request, pk):
  

    prestamo = get_object_or_404(Prestamo, pk=pk)

    if prestamo.detalles.filter(saldo_cuota=0).exists():
        messages.error(request, "No se puede editar un préstamo que ya tiene cuotas pagadas.")
        return redirect("rrhh:prestamo_detail", pk=prestamo.pk)

    if request.method == "POST":
        form = PrestamoForm(request.POST, instance=prestamo)

        if form.is_valid():
            prestamo = form.save(commit=False)
            prestamo.generar_prestamo()

            messages.success(request, f"Préstamo #{prestamo.id} actualizado correctamente.")
            return redirect("rrhh:prestamo_detail", pk=prestamo.pk)
    else:
        form = PrestamoForm(instance=prestamo)

    tasas_prestamo = {str(t.id): float(t.tasa_interes) for t in TipoPrestamo.objects.all()}

    return render(
        request,
        "rrhh/prestamo_form.html",
        {"form": form, "title": "Editar Préstamo", "tasas_prestamo": tasas_prestamo},
    )


@login_required
@permission_required('rrhh.view_prestamo', raise_exception=True)
def prestamo_detail(request, pk):
  

    prestamo = get_object_or_404(
        Prestamo.objects.select_related("empleado", "tipo_prestamo"), pk=pk
    )

    return render(request, "rrhh/prestamo_detail.html", {"prestamo": prestamo})


@login_required
@permission_required('rrhh.delete_prestamo', raise_exception=True)
def prestamo_delete(request, pk):
  

    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        prestamo_id = prestamo.id
        prestamo.delete()
        messages.success(request, f"Préstamo #{prestamo_id} eliminado correctamente.")
        return redirect("rrhh:prestamo_list")

    return render(request, "rrhh/prestamo_confirm_delete.html", {"prestamo": prestamo})


@login_required
@permission_required('rrhh.change_prestamo', raise_exception=True)
def prestamo_anular(request, pk):
  

    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        prestamo.anular()
        messages.success(request, f"Préstamo #{prestamo.id} anulado.")

    return redirect("rrhh:prestamo_detail", pk=prestamo.pk)


@login_required
@permission_required('rrhh.change_prestamodetalle', raise_exception=True)
def cuota_pagar(request, pk):


    cuota = get_object_or_404(PrestamoDetalle, pk=pk)

    if request.method == "POST":
        if cuota.prestamo.estado == "ANU":
            messages.error(request, "El préstamo está anulado, no se pueden pagar cuotas.")
        elif cuota.pagada:
            messages.error(request, "Esa cuota ya estaba pagada.")
        else:
            cuota.pagar()
            messages.success(request, f"Cuota {cuota.numero_cuota} pagada correctamente.")

    return redirect("rrhh:prestamo_detail", pk=cuota.prestamo_id)
