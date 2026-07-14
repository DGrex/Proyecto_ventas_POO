from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from shared.mixins import GroupRequiredMixin, StaffRequiredMixin, PermissionOrRedirectMixin
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
class FacturaPendienteListView(LoginRequiredMixin, GroupRequiredMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'billing.view_invoice'
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
class CobroListView(LoginRequiredMixin, GroupRequiredMixin, PermissionOrRedirectMixin, ListView):
    permission_required = 'cobros.view_cobrofactura'
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
@require_POST
def paypal_crear_orden(request, factura_id):
    """Crea una orden de PayPal por el monto que el vendedor indique (validado contra el saldo)."""
    factura = get_object_or_404(Invoice, pk=factura_id)

    if factura.estado == 'ANULADA':
        return JsonResponse({'error': 'No se puede pagar una factura anulada.'}, status=400)

    try:
        body = json.loads(request.body)
        monto = Decimal(str(body.get('monto', '0')))
    except (json.JSONDecodeError, InvalidOperation):
        return JsonResponse({'error': 'Monto inválido.'}, status=400)

    if monto <= 0:
        return JsonResponse({'error': 'El monto debe ser mayor que cero.'}, status=400)
    if monto > factura.saldo:
        return JsonResponse({'error': f'El monto excede el saldo pendiente (${factura.saldo}).'}, status=400)

    try:
        orden = create_order(monto, currency='USD', reference_id=f'factura-{factura.id}')
        return JsonResponse({'id': orden['id']})
    except Exception as e:
        return JsonResponse({'error': f'Error al crear la orden en PayPal: {e}'}, status=502)


@login_required
@group_required('Administrador', 'Vendedor')
@permission_required('cobros.add_cobrofactura', raise_exception=True)
@require_POST
def paypal_capturar_orden(request, factura_id, order_id):
    """
    Captura la orden ya aprobada por el comprador en PayPal, y si es exitosa,
    crea el CobroFactura correspondiente (reutilizando comprobante + notificaciones).
    """
    factura = get_object_or_404(Invoice, pk=factura_id)

    try:
        resultado = capture_order(order_id)
    except Exception as e:
        return JsonResponse({'error': f'Error al capturar el pago en PayPal: {e}'}, status=502)

    status = resultado.get('status')
    if status != 'COMPLETED':
        return JsonResponse({'error': f'PayPal no completó el pago (estado: {status}).'}, status=400)

    captura = resultado['purchase_units'][0]['payments']['captures'][0]
    monto_capturado = Decimal(captura['amount']['value'])
    transaction_id = captura['id']

    if monto_capturado > factura.saldo:
        # Salvaguarda extrema: no debería pasar si validamos bien al crear la orden,
        # pero si el saldo cambió entre medio (ej. otro cobro concurrente), no dejamos
        # que se aplique un pago inconsistente.
        return JsonResponse({
            'error': 'El saldo de la factura cambió durante el proceso de pago. '
                     'Contacta a soporte con el ID de transacción: ' + transaction_id
        }, status=409)

    cobro = CobroFactura(
        factura=factura,
        fecha=timezone.localdate(),
        valor=monto_capturado,
        metodo_pago='paypal',
        referencia_externa=transaction_id,
        observacion=f'Pago procesado vía PayPal (Transacción: {transaction_id}).',
    )
    cobro.save()  # dispara la misma validación/recalculo de saldo que el flujo manual

    # ── Comprobante + notificaciones (mismo flujo que el registro manual) ──
    pdf_bytes = generate_cobro_receipt_pdf(cobro)
    send_cobro_receipt_email(cobro, pdf_bytes)
    send_cobro_whatsapp(cobro)

    messages.success(request, f'Pago de ${cobro.valor} vía PayPal registrado correctamente!')

    return JsonResponse({
        'success': True,
        'cobro_id': cobro.id,
        'redirect_url': f"{reverse('cobros:cobro_list', kwargs={'factura_id': factura.id})}?voucher={cobro.id}",
    })