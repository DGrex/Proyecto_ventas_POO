from django.db import models

# Create your models here.
from django.db import models
from django.templatetags.static import static
from shared.validators import validate_cedula_ec

class Brand(models.Model):
    """Marcas de productos."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre de la Marca')
    description = models.TextField(blank=True, null=True, verbose_name = 'Descripción')
    is_active = models.BooleanField(default=True, verbose_name = 'Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name = 'Actualizado el')
    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']
    def __str__(self): return self.name

class ProductGroup(models.Model):
    """Grupos/categorías de productos."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre del Grupo')
    is_active = models.BooleanField(default=True, verbose_name = 'Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name = 'Actualizado el')
    class Meta:
        verbose_name = 'Grupo de Productos'
        verbose_name_plural = 'Grupos de Productos'
        ordering = ['name']
    def __str__(self): return self.name

class Supplier(models.Model):
    """Proveedores. M2M con Product."""
    name = models.CharField(max_length=200, verbose_name='Nombre de la Empresa')
    contact_name = models.CharField(max_length=200, blank=True, null=True, verbose_name = 'Nombre de Contacto')
    email = models.EmailField(blank=True, null=True, verbose_name = 'Correo Electronico')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name = 'Teléfono')
    address = models.TextField(blank=True, null=True, verbose_name = 'Dirección')
    is_active = models.BooleanField(default=True, verbose_name = 'Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name = 'Actualizado el')
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']
    def __str__(self): return self.name

class Product(models.Model):
    """Productos. FK a Brand/Group, M2M a Supplier."""
    name = models.CharField(max_length=200, verbose_name='Nombre del Producto')
    description = models.TextField(blank=True, null=True, verbose_name = 'Descripción')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='productos', verbose_name = 'Marca')
    group = models.ForeignKey(ProductGroup, on_delete=models.PROTECT, related_name='Grupos', verbose_name = 'Grupo')
    suppliers = models.ManyToManyField(Supplier, related_name='products', blank=True, verbose_name = 'Proveedores')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name = 'Precio Unitario')
    stock = models.IntegerField(default=0, verbose_name = 'Stock')
    is_active = models.BooleanField(default=True, verbose_name = 'Activo')
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name='Imagen')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name = 'Actualizado el')
    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']
    def __str__(self): return f'{self.name} ({self.brand.name})'
    @property
    def balance(self):
        return self.unit_price * self.stock

    @property
    def photo(self):
        """Propiedad compatible que actúa como alias de image."""
        return self.image

    def get_photo_url(self):
        """Devuelve la URL de la foto del producto.
        Si el producto no tiene foto, devuelve una imagen por defecto.
        Se usa en el listado, detalle y formulario (crear/editar)."""
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return static('billing/img/no-photo.svg')

class Customer(models.Model):
    """Clientes. OneToOne con CustomerProfile."""
    dni = models.CharField(max_length=13, unique=True, verbose_name='DNI/RUC', validators=[validate_cedula_ec])
    first_name = models.CharField(max_length=100, verbose_name = 'Nombres')
    last_name = models.CharField(max_length=100, verbose_name = 'Apellidos')
    email = models.EmailField(blank=True, null=True, verbose_name = 'Correo Electronico')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name = 'Teléfono')
    address = models.TextField(blank=True, null=True, verbose_name = 'Dirección')
    is_active = models.BooleanField(default=True, verbose_name = 'Activo')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name = 'Creado el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name = 'Actualizado el')
    class Meta:
        ordering = ['last_name', 'first_name']
    def __str__(self): return f'{self.last_name} {self.first_name}'
    @property
    def full_name(self): return f'{self.first_name} {self.last_name}'

class CustomerProfile(models.Model):
    """Perfil extendido. OneToOne con Customer."""
    TAXPAYER = [('final','Final Consumer'),('ruc','RUC'),('rise','RISE')]
    PAYMENT = [('cash','Cash'),('credit_15','15 days'),('credit_30','30 days'),('credit_60','60 days')]
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='profile', verbose_name = 'Cliente')
    taxpayer_type = models.CharField(max_length=10, choices=TAXPAYER, default='final', verbose_name = 'Tipo de Contribuyente')
    payment_terms = models.CharField(max_length=15, choices=PAYMENT, default='cash', verbose_name = 'Términos de Pago')
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name = 'Límite de Crédito')
    notes = models.TextField(blank=True, null=True, verbose_name = 'Notas')
    class Meta: verbose_name = 'Perfil del Cliente'
    def __str__(self): return f'Perfil: {self.customer}'

class Invoice(models.Model):
    """Cabecera de factura."""
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='Facturas', verbose_name = 'Cliente')
    invoice_date = models.DateTimeField(auto_now_add=True, verbose_name = 'Fecha de Factura')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name = 'Subtotal')
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name = 'Impuesto')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name = 'Total')
    is_active = models.BooleanField(default=True, verbose_name = 'Activa')
    class Meta: ordering = ['-invoice_date']
    def __str__(self): return f'Factura #{self.id} - {self.customer}'

class InvoiceDetail(models.Model):
    """Líneas de factura."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='details', verbose_name = 'Factura')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='invoice_details', verbose_name = 'Producto')
    quantity = models.IntegerField(default=1, verbose_name = 'Cantidad')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name = 'Precio Unitario')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name = 'Subtotal')
    def __str__(self): return f'{self.product.name} x {self.quantity}'
    def save(self, *args, **kwargs):
        # Si es un nuevo detalle, restamos del stock del producto
        if self.pk is None:
            self.product.stock -= self.quantity
            self.product.save()
        else:
            # Si ya existía, ajustamos la diferencia
            try:
                original = InvoiceDetail.objects.get(pk=self.pk)
                diff = self.quantity - original.quantity
                self.product.stock -= diff
                self.product.save()
            except InvoiceDetail.DoesNotExist:
                pass
            
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)


from django.db.models.signals import post_delete
from django.dispatch import receiver

@receiver(post_delete, sender=InvoiceDetail)
def restore_stock_on_detail_delete(sender, instance, **kwargs):
    # Al eliminar un detalle (o la factura en cascada), devolvemos el stock al producto
    product = instance.product
    product.stock += instance.quantity
    product.save()


