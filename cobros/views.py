from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from shared.mixins import GroupRequiredMixin, StaffRequiredMixin
from shared.decorators import audit_action
from shared.notifications import (
    generate_cobro_receipt_pdf, send_cobro_receipt_email, send_cobro_whatsapp
)
from billing.models import Invoice
from .models import CobroFactura
from .forms import CobroFacturaForm


# 1) Lista de facturas a crédito (por defecto muestra PENDIENTE, con filtro de estado)
@method_decorator(audit_action('LIST_FACTURAS_PENDIENTES'), name='dispatch')
class FacturaPendienteListView(LoginRequiredMixin, GroupRequiredMixin, ListView):
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    template_name = 'cobros/factura_pendiente_list.html'
    context_object_name = 'facturas'
    paginate_by = 10

    def get_queryset(self):
        qs = Invoice.objects.filter(tipo_pago='credito').select_related('customer')

        estado = self.request.GET.get('estado', 'PENDIENTE')
        if estado and estado != 'TODOS':
            qs = qs.filter(estado=estado)

        dni = self.request.GET.get('dni')
        if dni:
            qs = qs.filter(customer__dni=dni)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estado_filter'] = self.request.GET.get('estado', 'PENDIENTE')
        return ctx


# 2) Registrar pago (uno o varios abonos: cada envío del form = un abono)
@method_decorator(audit_action('CREATE_COBRO'), name='dispatch')
class CobroCreateView(LoginRequiredMixin, GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Vendedor']
    model = CobroFactura
    form_class = CobroFacturaForm
    template_name = 'cobros/cobro_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.factura = get_object_or_404(Invoice, pk=kwargs['factura_id'])
        if self.factura.estado == 'ANULADA':
            messages.error(request, 'No se puede pagar una factura anulada.')
            return redirect('cobros:factura_pendiente_list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['factura'] = self.factura
        return kwargs

    def form_valid(self, form):
        form.instance.factura = self.factura
        self.object = form.save()

        # ── Comprobante + notificaciones (mejor esfuerzo, no bloquean el guardado) ──
        pdf_bytes = generate_cobro_receipt_pdf(self.object)

        ok_email, msg_email = send_cobro_receipt_email(self.object, pdf_bytes)
        if ok_email:
            messages.info(self.request, '📧 Comprobante de abono enviado al correo del cliente.')
        else:
            messages.warning(self.request, f'No se pudo enviar el correo: {msg_email}')

        ok_wa, msg_wa = send_cobro_whatsapp(self.object)
        if ok_wa:
            messages.info(self.request, '📱 Confirmación enviada por WhatsApp.')
        else:
            messages.warning(self.request, f'No se pudo enviar WhatsApp: {msg_wa}')

        messages.success(self.request, f'Abono de ${self.object.valor} registrado correctamente!')
        url = reverse('cobros:cobro_list', kwargs={'factura_id': self.factura.id})
        return redirect(f'{url}?voucher={self.object.pk}')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['factura'] = self.factura
        ctx['title'] = f'Registrar Pago - Factura #{self.factura.id}'
        return ctx

    def get_success_url(self):
        return reverse('cobros:cobro_list', kwargs={'factura_id': self.factura.id})


# 3) Historial de pagos de una factura
@method_decorator(audit_action('LIST_COBROS'), name='dispatch')
class CobroListView(LoginRequiredMixin, GroupRequiredMixin, ListView):
    group_required = ['Administrador', 'Vendedor']
    model = CobroFactura
    template_name = 'cobros/cobro_list.html'
    context_object_name = 'cobros'
    paginate_by = 10

    def dispatch(self, request, *args, **kwargs):
        self.factura = get_object_or_404(Invoice, pk=kwargs['factura_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return CobroFactura.objects.filter(factura=self.factura)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['factura'] = self.factura
        return ctx


# 4) Editar pago
@method_decorator(audit_action('UPDATE_COBRO'), name='dispatch')
class CobroUpdateView(LoginRequiredMixin, GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Vendedor']
    model = CobroFactura
    form_class = CobroFacturaForm
    template_name = 'cobros/cobro_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['factura'] = self.object.factura
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['factura'] = self.object.factura
        ctx['title'] = 'Editar Pago'
        return ctx

    def get_success_url(self):
        messages.success(self.request, 'Pago actualizado correctamente!')
        return reverse('cobros:cobro_list', kwargs={'factura_id': self.object.factura_id})


@login_required
@xframe_options_sameorigin
def cobro_comprobante_pdf(request, pk):
    """Sirve el comprobante de abono en PDF, embebido (inline) para el modal."""
    cobro = get_object_or_404(
        CobroFactura.objects.select_related('factura__customer'), pk=pk
    )
    pdf_bytes = generate_cobro_receipt_pdf(cobro)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="comprobante_abono_{cobro.id}.pdf"'
    return response


# 5) Eliminar pago (solo si la factura no está totalmente pagada... o si al
#    eliminar no rompe la consistencia). Regla pedida: "no permitir eliminar
#    un pago cuando deje inconsistente el saldo" -> aquí sencillamente NO hay
#    forma de dejarlo inconsistente porque el modelo repone el saldo, pero sí
#    debemos impedir eliminar cobros de facturas ya PAGADAS si eso reabriría
#    pagos ya reconciliados contablemente (regla de negocio típica).
@method_decorator(audit_action('DELETE_COBRO'), name='dispatch')
class CobroDeleteView(LoginRequiredMixin, GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador']
    model = CobroFactura
    template_name = 'cobros/cobro_confirm_delete.html'
    staff_redirect_url = '/cobros/'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.factura.estado == 'PAGADA':
            messages.error(
                request,
                'No se puede eliminar un pago de una factura ya cancelada '
                '(edite el pago en vez de eliminarlo, o contacte a contabilidad).'
            )
            return redirect('cobros:cobro_list', factura_id=self.object.factura_id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, f'Pago de ${self.object.valor} eliminado correctamente!')
        return reverse('cobros:cobro_list', kwargs={'factura_id': self.object.factura_id})