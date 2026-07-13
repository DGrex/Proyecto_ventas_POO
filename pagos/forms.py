from django import forms
from django.utils import timezone
from .models import PagoCompra


class PagoCompraForm(forms.ModelForm):
    class Meta:
        model = PagoCompra
        # 'fecha' NO es editable por el usuario: la asigna el sistema
        # automáticamente (ver __init__) y nunca se muestra como input.
        fields = ['valor', 'observacion']
        labels = {
            'valor': 'Valor a Abonar ($)',
            'observacion': 'Observación',
        }
        widgets = {
            'valor': forms.NumberInput(attrs={'class': 'form-control form-control-premium', 'step': '0.01', 'min': '0.01'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control form-control-premium', 'rows': 2}),
        }

    def __init__(self, *args, compra=None, **kwargs):
        self.compra = compra
        super().__init__(*args, **kwargs)
        if compra and not self.instance.pk:
            self.instance.compra = compra
        # Al crear un pago nuevo, la fecha siempre es la del sistema (hoy).
        # Al editar uno existente, se conserva la fecha original y tampoco
        # es editable desde el formulario.
        if not self.instance.pk:
            self.instance.fecha = timezone.localdate()

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