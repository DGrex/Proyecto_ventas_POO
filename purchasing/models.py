from django.db import models
from decimal import Decimal
from django.db.models.signals import post_delete
from django.dispatch import receiver
from billing.models import Supplier, Product   # Reutilizamos modelos de billing

class Purchase(models.Model):
    """Cabecera de compra. Documenta una adquisición a un proveedor."""
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name='purchases', verbose_name='Proveedor'
    )
    document_number = models.CharField(
        max_length=20, verbose_name='Nº de Factura Proveedor'
    )
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Compra')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Impuesto (15%)')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Total')
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'
        ordering = ['-purchase_date']
        # Evitar facturas de proveedor duplicadas para el mismo proveedor (Reto 2)
        unique_together = ['supplier', 'document_number']

    def __str__(self):
        return f'Compra #{self.id} - {self.supplier}'


class PurchaseDetail(models.Model):
    """Líneas de compra. Cada fila es un producto adquirido."""
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name='details', verbose_name='Compra'
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='purchase_details', verbose_name='Producto'
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Cantidad')
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Costo Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Subtotal')

    class Meta:
        verbose_name = 'Detalle de Compra'
        verbose_name_plural = 'Detalles de Compra'

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs):
        # Primero calculamos el subtotal de esta línea
        self.subtotal = self.quantity * self.unit_cost
        
        # Reto 1: Actualizar stock sumando la cantidad de la compra
        if self.pk is None:
            # Si es nuevo, sumamos la cantidad ingresada al stock
            self.product.stock += self.quantity
            self.product.save()
        else:
            # Si es una actualización, calculamos la diferencia y la ajustamos
            try:
                original = PurchaseDetail.objects.get(pk=self.pk)
                diff = self.quantity - original.quantity
                self.product.stock += diff
                self.product.save()
            except PurchaseDetail.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)


@receiver(post_delete, sender=PurchaseDetail)
def restore_stock_on_purchase_detail_delete(sender, instance, **kwargs):
    # Al eliminar una línea de compra (o la compra en cascada), restamos la cantidad del stock del producto
    product = instance.product
    product.stock -= instance.quantity
    product.save()
