from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from purchasing.models import Purchase


class PagoCompra(models.Model):
    compra = models.ForeignKey(
        Purchase,
        on_delete=models.PROTECT,
        related_name='pagos',
        verbose_name='Compra'
    )
    fecha = models.DateField(verbose_name='Fecha de Pago')
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Valor Abonado')
    observacion = models.TextField(blank=True, verbose_name='Observación')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de Compra'
        verbose_name_plural = 'Pagos de Compras'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Pago ${self.valor} - Compra #{self.compra_id}'

    def clean(self):
        if not self.compra_id:
            return  # todavía no hay compra asignada, nada que validar aún

        if self.compra.estado == 'ANULADA':
            raise ValidationError('No se puede registrar un pago sobre una compra anulada.')
        if self.valor is None or self.valor <= 0:
            raise ValidationError('El valor del pago debe ser mayor que cero.')

        saldo_disponible = self.compra.saldo
        if self.pk:
            original = PagoCompra.objects.get(pk=self.pk)
            saldo_disponible += original.valor

        if self.valor > saldo_disponible:
            raise ValidationError(f'El pago excede el saldo pendiente (${saldo_disponible}).')

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        if not is_new:
            original = PagoCompra.objects.get(pk=self.pk)
            diferencia = self.valor - original.valor
        else:
            diferencia = self.valor

        super().save(*args, **kwargs)

        compra = self.compra
        compra.saldo = compra.saldo - diferencia
        compra.estado = 'PAGADA' if compra.saldo == Decimal('0') else 'PENDIENTE'
        compra.save(update_fields=['saldo', 'estado'])

    def delete(self, *args, **kwargs):
        compra = self.compra
        valor = self.valor
        super().delete(*args, **kwargs)
        compra.saldo = compra.saldo + valor
        compra.estado = 'PAGADA' if compra.saldo == Decimal('0') else 'PENDIENTE'
        compra.save(update_fields=['saldo', 'estado'])