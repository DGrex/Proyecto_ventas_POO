from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from shared.mixins import GroupRequiredMixin, StaffRequiredMixin, PermissionOrRedirectMixin, ExportMixin
from shared.decorators import audit_action, group_required
from shared.notifications import (
    generate_cobro_receipt_pdf, send_cobro_receipt_email, send_cobro_whatsapp
)
from billing.models import Invoice
from .models import CobroFactura
from .forms import CobroFacturaForm

import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from shared.paypal import create_order, capture_order
from django.conf import settings
from django.utils import timezone 


# 1) Lista de facturas a crédito (por defecto muestra PENDIENTE, con filtro de estado)
@method_decorator(audit_action('LIST_FACTURAS_PENDIENTES'), name='dispatch')
class FacturaPendienteListView(LoginRequiredMixin, ExportMixin, GroupRequiredMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'billing.view_invoice'
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    template_name = 'cobros/factura_pendiente_list.html'
    context_object_name = 'facturas'
    paginate_by = 10
    export_filename = 'facturas_pendientes'
    export_fields = [
        ('id', 'ID'),
        ('customer.full_name', 'Cliente'),
        ('invoice_date', 'Fecha de Factura'),
        ('total', 'Total'),
        ('saldo', 'Saldo Pendiente'),
        ('estado', 'Estado'),
    ]

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
class CobroCreateView(LoginRequiredMixin, GroupRequiredMixin, PermissionOrRedirectMixin, CreateView):
    permission_required = 'cobros.add_cobrofactura'
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
        ctx['paypal_client_id'] = settings.PAYPAL_CLIENT_ID
        return ctx

    def get_success_url(self):
        return reverse('cobros:cobro_list', kwargs={'factura_id': self.factura.id})


# 3) Historial de pagos de una factura
@method_decorator(audit_action('LIST_COBROS'), name='dispatch')
class CobroListView(LoginRequiredMixin, ExportMixin, GroupRequiredMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'cobros.view_cobrofactura'
    group_required = ['Administrador', 'Vendedor']
    model = CobroFactura
    template_name = 'cobros/cobro_list.html'
    context_object_name = 'cobros'
    paginate_by = 10
    export_filename = 'historial_cobros'
    export_fields = [
        ('fecha', 'Fecha de Pago'),
        ('valor', 'Valor Abonado'),
        ('metodo_pago', 'Método de Pago'),
        ('referencia_externa', 'Referencia Externa'),
        ('observacion', 'Observación'),
    ]

    def dispatch(self, request, *args, **kwargs):
        self.factura = get_object_or_404(Invoice, pk=kwargs['factura_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = CobroFactura.objects.filter(factura=self.factura)
        p = self.request.GET
        if p.get('metodo_pago'):
            qs = qs.filter(metodo_pago=p['metodo_pago'])
        if p.get('fecha_min'):
            qs = qs.filter(fecha__gte=p['fecha_min'])
        if p.get('fecha_max'):
            qs = qs.filter(fecha__lte=p['fecha_max'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['factura'] = self.factura
        ctx['filter'] = self.request.GET
        filter_keys = ['metodo_pago', 'fecha_min', 'fecha_max']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        return ctx


# 4) Editar pago
@method_decorator(audit_action('UPDATE_COBRO'), name='dispatch')
class CobroUpdateView(LoginRequiredMixin, GroupRequiredMixin, PermissionOrRedirectMixin, UpdateView):
    permission_required = 'cobros.change_cobrofactura'
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
@permission_required('cobros.view_cobrofactura', raise_exception=True)
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


@method_decorator(audit_action('DELETE_COBRO'), name='dispatch')
class CobroDeleteView(LoginRequiredMixin, GroupRequiredMixin, StaffRequiredMixin, PermissionOrRedirectMixin, DeleteView):
    permission_required = 'cobros.delete_cobrofactura'
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


@login_required
@group_required('Administrador', 'Vendedor')
@permission_required('cobros.add_cobrofactura', raise_exception=True)
def paypal_iniciar_pago(request, factura_id):
    """Crea la orden en PayPal y redirige al navegador directamente a la página de aprobación (sin popup)."""
    factura = get_object_or_404(Invoice, pk=factura_id)

    if factura.estado == 'ANULADA':
        messages.error(request, 'No se puede pagar una factura anulada.')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    monto = request.POST.get('monto') or factura.saldo
    try:
        monto = Decimal(str(monto))
    except InvalidOperation:
        messages.error(request, 'Monto inválido.')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    if monto <= 0 or monto > factura.saldo:
        messages.error(request, f'El monto debe ser mayor a 0 y no exceder el saldo (${factura.saldo}).')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    return_url = request.build_absolute_uri(
        reverse('cobros:paypal_retorno', kwargs={'factura_id': factura.id})
    )
    cancel_url = request.build_absolute_uri(
        reverse('cobros:cobro_create', kwargs={'factura_id': factura.id})
    )

    try:
        orden = create_order(monto, currency='USD', reference_id=f'factura-{factura.id}',
                              return_url=return_url, cancel_url=cancel_url)
    except Exception as e:
        messages.error(request, f'Error al conectar con PayPal: {e}')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    # Buscamos el link de aprobación que PayPal nos devuelve y navegamos ahí directamente
    approve_link = next((l['href'] for l in orden['links'] if l['rel'] == 'approve'), None)
    if not approve_link:
        messages.error(request, 'PayPal no devolvió un link de aprobación válido.')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    return redirect(approve_link)


@login_required
@group_required('Administrador', 'Vendedor')
@permission_required('cobros.add_cobrofactura', raise_exception=True)
def paypal_retorno(request, factura_id):
    """PayPal redirige aquí después de que el cliente aprueba el pago (?token=<order_id>)."""
    factura = get_object_or_404(Invoice, pk=factura_id)
    order_id = request.GET.get('token')

    if not order_id:
        messages.error(request, 'No se recibió el identificador de la orden de PayPal.')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    try:
        resultado = capture_order(order_id)
    except Exception as e:
        messages.error(request, f'Error al capturar el pago en PayPal: {e}')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    if resultado.get('status') != 'COMPLETED':
        messages.error(request, f"PayPal no completó el pago (estado: {resultado.get('status')}).")
        return redirect('cobros:cobro_create', factura_id=factura.id)

    captura = resultado['purchase_units'][0]['payments']['captures'][0]
    monto_capturado = Decimal(captura['amount']['value'])
    transaction_id = captura['id']

    if monto_capturado > factura.saldo:
        messages.error(request, f'El saldo cambió durante el pago. Transacción PayPal: {transaction_id}. Contacta a soporte.')
        return redirect('cobros:cobro_create', factura_id=factura.id)

    cobro = CobroFactura(
        factura=factura,
        fecha=timezone.localdate(),
        valor=monto_capturado,
        metodo_pago='paypal',
        referencia_externa=transaction_id,
        observacion=f'Pago procesado vía PayPal (Transacción: {transaction_id}).',
    )
    cobro.save()

    pdf_bytes = generate_cobro_receipt_pdf(cobro)
    send_cobro_receipt_email(cobro, pdf_bytes)
    send_cobro_whatsapp(cobro)

    messages.success(request, f'Pago de ${cobro.valor} vía PayPal registrado correctamente!')
    return redirect(f"{reverse('cobros:cobro_list', kwargs={'factura_id': factura.id})}?voucher={cobro.id}")