from django import forms
from django.utils import timezone
from .models import CobroFactura


class CobroFacturaForm(forms.ModelForm):
    class Meta:
        model = CobroFactura
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

    def __init__(self, *args, factura=None, **kwargs):
        self.factura = factura
        super().__init__(*args, **kwargs)
        if factura and not self.instance.pk:
            self.instance.factura = factura
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
        factura = self.factura or getattr(self.instance, 'factura', None)
        if factura and valor is not None:
            saldo_disponible = factura.saldo
            if self.instance.pk:
                saldo_disponible += self.instance.valor
            if valor > saldo_disponible:
                raise forms.ValidationError(f'El pago (${valor}) supera el saldo pendiente (${saldo_disponible}).')
            if factura.estado == 'ANULADA':
                raise forms.ValidationError('No se puede pagar una factura anulada.')
        return cleaned