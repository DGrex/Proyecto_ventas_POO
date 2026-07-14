from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from billing.models import Invoice


class CobroFactura(models.Model):
    METODO_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('paypal', 'PayPal'),
        ('tarjeta', 'Tarjeta'),
    ]

    factura = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='cobros', verbose_name='Factura'
    )
    fecha = models.DateField(verbose_name='Fecha de Pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Abonado')
    metodo_pago = models.CharField(
        max_length=15, choices=METODO_PAGO, default='efectivo', verbose_name='Método de Pago'
    )
    referencia_externa = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name='Referencia Externa',
        help_text='ID de transacción de PayPal u otro medio externo, para trazabilidad.'
    )
    observacion = models.TextField(blank=True, verbose_name='Observación')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cobro de Factura'
        verbose_name_plural = 'Cobros de Facturas'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Cobro ${self.valor} - Factura #{self.factura_id}'

    def clean(self):
        if not self.factura_id:
            return  # todavía no hay factura asignada, nada que validar aún

        if self.factura.estado == 'ANULADA':
            raise ValidationError('No se puede registrar un pago sobre una factura anulada.')
        if self.valor is None or self.valor <= 0:
            raise ValidationError('El valor del pago debe ser mayor que cero.')

        saldo_disponible = self.factura.saldo
        if self.pk:
            original = CobroFactura.objects.get(pk=self.pk)
            saldo_disponible += original.valor

        if self.valor > saldo_disponible:
            raise ValidationError(f'El pago excede el saldo pendiente (${saldo_disponible}).')

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        if not is_new:
            original = CobroFactura.objects.get(pk=self.pk)
            diferencia = self.valor - original.valor
        else:
            diferencia = self.valor

        super().save(*args, **kwargs)

        factura = self.factura
        factura.saldo = factura.saldo - diferencia
        factura.estado = 'PAGADA' if factura.saldo == Decimal('0') else 'PENDIENTE'
        factura.save(update_fields=['saldo', 'estado'])

    def delete(self, *args, **kwargs):
        factura = self.factura
        valor = self.valor
        super().delete(*args, **kwargs)
        factura.saldo = factura.saldo + valor
        factura.estado = 'PAGADA' if factura.saldo == Decimal('0') else 'PENDIENTE'
        factura.save(update_fields=['saldo', 'estado'])