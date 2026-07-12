from django import forms
from django.forms import inlineformset_factory
from .models import Purchase, PurchaseDetail
from billing.models import Supplier, Product

class PurchaseForm(forms.ModelForm):
    """Formulario premium para la cabecera de compra."""
    class Meta:
        model = Purchase
        fields = ['supplier', 'document_number', 'tipo_pago']
        labels = {
            'supplier': 'Proveedor',
            'document_number': 'Nº Factura Proveedor',
            'tipo_pago': 'Tipo de Pago',
        }
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select form-select-premium'}),
            'document_number': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: INV-001-2026'
            }),
            'tipo_pago': forms.Select(attrs={'class': 'form-select form-select-premium'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar proveedores activos
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        if self.is_bound and self.errors:
            for field_name in self.errors:
                if field_name in self.fields:
                    current_class = self.fields[field_name].widget.attrs.get('class', '')
                    if 'is-invalid' not in current_class:
                        self.fields[field_name].widget.attrs['class'] = f"{current_class} is-invalid"

class PurchaseDetailForm(forms.ModelForm):
    class Meta:
        model = PurchaseDetail
        fields = ['product', 'quantity', 'unit_cost']

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return qty

    def clean_unit_cost(self):
        cost = self.cleaned_data.get('unit_cost')
        if cost is None or cost <= 0:
            raise forms.ValidationError('El costo unitario debe ser mayor que cero.')
        return cost

PurchaseDetailFormSet = inlineformset_factory(
    Purchase,
    PurchaseDetail,
    fields=['product', 'quantity', 'unit_cost'],
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select form-select-premium detail-product'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-premium detail-quantity', 'min': 1}),
        'unit_cost': forms.NumberInput(attrs={
            'class': 'form-control form-control-premium detail-cost',
            'step': '0.01', 'min': '0.01', 'placeholder': '0.00'
        }),
    }
)