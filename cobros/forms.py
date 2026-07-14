from django import forms
from django.utils import timezone
from .models import CobroFactura


class CobroFacturaForm(forms.ModelForm):
    class Meta:
        model = CobroFactura
        fields = ['valor', 'metodo_pago', 'observacion']
        labels = {
            'valor': 'Valor a Abonar ($)',
            'metodo_pago': 'Método de Pago',
            'observacion': 'Observación',
        }
        widgets = {
            'valor': forms.NumberInput(attrs={'class': 'form-control form-control-premium', 'step': '0.01', 'min': '0.01'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select form-select-premium'}),
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
        # "PayPal" no debe elegirse a mano en el registro manual: solo se
        # asigna automáticamente cuando el pago viene de la captura real
        # de PayPal. Si el cobro YA es de PayPal (edición), se respeta.
        if self.instance.metodo_pago != 'paypal':
            self.fields['metodo_pago'].choices = [
                c for c in CobroFactura.METODO_PAGO if c[0] != 'paypal'
            ]

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