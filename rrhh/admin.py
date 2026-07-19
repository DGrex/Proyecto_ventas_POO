from django.contrib import admin

from .models import Empleado, Prestamo, PrestamoDetalle, TipoPrestamo


@admin.register(TipoPrestamo)
class TipoPrestamoAdmin(admin.ModelAdmin):
    list_display = ("id", "descripcion", "tasa_interes")


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombres", "sueldo")


class PrestamoDetalleInline(admin.TabularInline):
    model = PrestamoDetalle
    extra = 0
    readonly_fields = ("numero_cuota", "fecha_vencimiento", "valor_cuota", "saldo_cuota")
    can_delete = False


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "empleado", "tipo_prestamo", "fecha_prestamo",
        "monto", "interes", "monto_pagar", "saldo", "estado",
    )
    list_filter = ("estado", "tipo_prestamo")
    readonly_fields = ("interes", "monto_pagar", "saldo")
    inlines = [PrestamoDetalleInline]
