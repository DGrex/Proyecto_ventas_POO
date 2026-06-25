from django import forms
from django.forms import inlineformset_factory
from .models import Purchase, PurchaseDetail
from billing.models import Supplier, Product

class PurchaseForm(forms.ModelForm):
    """Formulario premium para la cabecera de compra."""
    class Meta:
        model = Purchase
        fields = ['supplier', 'document_number']
        labels = {
            'supplier': 'Proveedor',
            'document_number': 'Nº Factura Proveedor',
        }
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select form-select-premium'}),
            'document_number': forms.TextInput(attrs={
                'class': 'form-control form-control-premium',
                'placeholder': 'Ej: INV-001-2026'
            }),
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


PurchaseDetailFormSet = inlineformset_factory(
    Purchase,
    PurchaseDetail,
    fields=['product', 'quantity', 'unit_cost'],
    extra=1,  # Usamos 1 fila vacía inicial
    can_delete=True,
    widgets={
        'product': forms.Select(attrs={'class': 'form-select form-select-premium detail-product'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-premium detail-quantity', 'min': 1}),
        'unit_cost': forms.NumberInput(attrs={'class': 'form-control form-control-premium detail-cost', 'step': '0.01', 'placeholder': '0.00'}),
    }
)
