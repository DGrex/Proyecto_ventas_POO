from django import forms
from .models import PagoCompra


class PagoCompraForm(forms.ModelForm):
    class Meta:
        model = PagoCompra
        fields = ['fecha', 'valor', 'observacion']
        labels = {
            'fecha': 'Fecha de Pago',
            'valor': 'Valor a Abonar ($)',
            'observacion': 'Observación',
        }
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-premium'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control form-control-premium', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control form-control-premium', 'rows': 2}),
        }

    def __init__(self, *args, compra=None, **kwargs):
        self.compra = compra
        super().__init__(*args, **kwargs)
        if compra and not self.instance.pk:
            self.instance.compra = compra

    def clean_valor(self):
        valor = self.cleaned_data.get('valor')
        if valor is None or valor <= 0:
            raise forms.ValidationError('El valor debe ser mayor que cero.')
        return valor

    def clean(self):
        cleaned = super().clean()
        valor = cleaned.get('valor')
        compra = self.compra or getattr(self.instance, 'compra', None)
        if compra and valor is not None:
            saldo_disponible = compra.saldo
            if self.instance.pk:
                saldo_disponible += self.instance.valor
            if valor > saldo_disponible:
                raise forms.ValidationError(f'El pago (${valor}) supera el saldo pendiente (${saldo_disponible}).')
            if compra.estado == 'ANULADA':
                raise forms.ValidationError('No se puede pagar una compra anulada.')
        return cleaned