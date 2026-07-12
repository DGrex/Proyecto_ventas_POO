from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import Brand, Product, ProductGroup, Supplier, Invoice, InvoiceDetail, Customer


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class':'form-control'}))
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class':'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class':'form-control'}))
    class Meta:
        model = User
        fields = ['username','first_name','last_name','email','password1','password2']
        labels = {'username':'Nombre de usuario', 'first_name':'Nombre', 'last_name':'Apellido', 'email':'Correo electrónico', 'password1':'Contraseña', 'password2':'Confirmar contraseña'}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Nombre de usuario'
        self.fields['first_name'].label = 'Nombre'
        self.fields['last_name'].label = 'Apellido'
        self.fields['email'].label = 'Correo electrónico'
        self.fields['password1'].label = 'Contraseña'
        self.fields['password2'].label = 'Confirmar contraseña'
        
        for f in self.fields: self.fields[f].widget.attrs['class'] = 'form-control'

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'description', 'is_active']
        labels = {'name': 'Nombre de la marca', 'description': 'Descripción', 'is_active': '¿Está activa?'}
        widgets = {
            'name': forms.TextInput(attrs={'class':'form-control'}),
            'description': forms.Textarea(attrs={'class':'form-control','rows':3}),
            'is_active': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }

        
class InvoiceForm(forms.ModelForm):
    """Formulario premium para la cabecera de factura."""
    class Meta:
        model = Invoice
        fields = ['customer', 'tipo_pago']
        labels = {
            'customer': 'Cliente',
            'tipo_pago': 'Tipo de Pago',
        }
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'form-select form-select-premium',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar clientes activos en la creación/edición
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        if self.is_bound and self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    current_class = self.fields[field_name].widget.attrs.get('class', '')
                    if 'is-invalid' not in current_class:
                        self.fields[field_name].widget.attrs['class'] = f"{current_class} is-invalid"


# Formset premium: permite agregar MÚLTIPLES detalles dentro de UNA factura
InvoiceDetailFormSet = inlineformset_factory(
    Invoice,           # Modelo padre
    InvoiceDetail,     # Modelo hijo
    fields=['product', 'quantity', 'unit_price'],
    extra=1,           # Empezar con 1 fila por defecto
    can_delete=True,   # Checkbox para eliminar filas
    widgets={
        'product': forms.Select(attrs={'class': 'form-select form-select-premium detail-product'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-premium detail-quantity', 'min': 1}),
        'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-premium detail-price', 'step': '0.01', 'readonly': 'readonly'}),
    }
)


class ProductForm(forms.ModelForm):
    """
    Formulario premium para la creación y edición de productos.
    Centraliza widgets, validaciones, estilos Bootstrap modernos y lógica visual.
    """
    class Meta:
        model = Product
        fields = ['name', 'description', 'brand', 'group', 'suppliers', 'unit_price', 'stock', 'image', 'is_active']
        labels = {
            'name': 'Nombre del producto',
            'description': 'Descripción',
            'brand': 'Marca',
            'group': 'Categoría (Grupo)',
            'suppliers': 'Proveedores',
            'unit_price': 'Precio unitario ($)',
            'stock': 'Stock disponible',
            'image': 'Imagen del producto',
            'is_active': 'Estado activo'
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: Arroz Integral 5kg'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control form-control-premium',
                'rows': 3,
                'placeholder': 'Describa el producto, características principales, etc...'
            }),
            'brand': forms.Select(attrs={
                'class': 'form-select form-select-premium'
            }),
            'group': forms.Select(attrs={
                'class': 'form-select form-select-premium'
            }),
            'suppliers': forms.SelectMultiple(attrs={
                'class': 'form-select form-select-premium',
                'size': '4'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control form-control-premium',
                'step': '0.01',
                'placeholder': '0.00',
                'min': '0.01'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-control form-control-premium',
                'min': '0',
                'placeholder': '0'
            }),
            'image': forms.FileInput(attrs={
                'class': 'd-none',
                'id': 'product-image-input',
                'accept': 'image/*'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch'
            }),
        }
        help_texts = {
            'name': 'Ingrese el nombre comercial o técnico del producto.',
            'description': 'Breve descripción de las características del producto.',
            'brand': 'Seleccione la marca fabricante.',
            'group': 'Seleccione la categoría o grupo al que pertenece.',
            'suppliers': 'Seleccione uno o más proveedores (Ctrl+clic para selección múltiple).',
            'unit_price': 'Precio de venta al público en USD (debe ser mayor que cero).',
            'stock': 'Cantidad disponible actualmente en inventario.',
            'image': 'Suba una imagen del producto (formatos válidos: JPG, PNG, WebP).',
            'is_active': 'Define si el producto está activo para la venta.'
        }
        error_messages = {
            'name': {
                'required': 'El nombre del producto es obligatorio.',
            },
            'brand': {
                'required': 'Debe seleccionar una marca.',
            },
            'group': {
                'required': 'Debe seleccionar una categoría.',
            },
            'unit_price': {
                'required': 'El precio unitario es obligatorio.',
                'invalid': 'Ingrese un valor numérico válido.',
            },
            'stock': {
                'required': 'El stock es obligatorio.',
                'invalid': 'Ingrese un número entero válido.',
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    current_class = self.fields[field_name].widget.attrs.get('class', '')
                    if 'is-invalid' not in current_class:
                        self.fields[field_name].widget.attrs['class'] = f"{current_class} is-invalid"

    def clean_unit_price(self):
        unit_price = self.cleaned_data.get('unit_price')
        if unit_price is not None and unit_price <= 0:
            raise forms.ValidationError("El precio unitario debe ser mayor que cero.")
        return unit_price


class CustomerForm(forms.ModelForm):
    """
    Formulario premium para la creación y edición de clientes.
    Centraliza widgets, validaciones, estilos Bootstrap modernos y lógica visual.
    Sigue el mismo patrón que ProductForm.
    """

    class Meta:
        model = Customer
        fields = ['dni', 'first_name', 'last_name', 'email', 'phone', 'address', 'is_active','whatsapp_apikey']
        labels = {
            'dni': 'DNI / RUC',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
            'phone': 'Teléfono',
             'whatsapp_apikey': 'WhatsApp API Key',
            'address': 'Dirección',
            'is_active': 'Estado activo',
        }
        widgets = {
            'dni': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: 0912345678',
                'maxlength': '13',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: Juan Carlos',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: Pérez García',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: cliente@correo.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: 0991234567',
                'maxlength': '20',
            }),
            'whatsapp_apikey': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: 123456 (opcional)',
                'maxlength': '20',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control form-control-premium',
                'rows': 3,
                'placeholder': 'Ej: Av. Principal 123, Ciudad, País',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'role': 'switch',
            }),
        }
        help_texts = {
            'dni': 'Ingrese el número de cédula (10 dígitos) o RUC (13 dígitos).',
            'first_name': 'Nombre(s) completo(s) del cliente.',
            'last_name': 'Apellido(s) completo(s) del cliente.',
            'email': 'Correo electrónico de contacto (opcional).',
            'phone': 'Número de teléfono o celular de contacto (opcional).',
            'whatsapp_apikey': 'Opcional, El cliente debe suscribirse primero al bot.',
            'address': 'Dirección física o postal del cliente (opcional).',
            'is_active': 'Define si el cliente está activo en el sistema.',
        }
        error_messages = {
            'dni': {
                'required': 'El DNI/RUC es obligatorio.',
                'unique': 'Ya existe un cliente registrado con este DNI/RUC.',
            },
            'first_name': {
                'required': 'El nombre es obligatorio.',
            },
            'last_name': {
                'required': 'El apellido es obligatorio.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    current_class = self.fields[field_name].widget.attrs.get('class', '')
                    if 'is-invalid' not in current_class:
                        self.fields[field_name].widget.attrs['class'] = f"{current_class} is-invalid"

