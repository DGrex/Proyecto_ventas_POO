from django import forms

from .models import Prestamo


class PrestamoForm(forms.ModelForm):

    class Meta:
        model = Prestamo
        fields = ["empleado", "tipo_prestamo", "monto", "numero_cuotas"]
        labels = {
            "empleado": "Empleado",
            "tipo_prestamo": "Tipo de préstamo",
            "monto": "Monto solicitado",
            "numero_cuotas": "Número de cuotas",
        }
        widgets = {
            "empleado": forms.Select(attrs={"class": "form-select"}),
            "tipo_prestamo": forms.Select(attrs={"class": "form-select"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "numero_cuotas": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor que cero.")
        return monto

    def clean_numero_cuotas(self):
        numero_cuotas = self.cleaned_data.get("numero_cuotas")
        if numero_cuotas is None or numero_cuotas <= 0:
            raise forms.ValidationError("El número de cuotas debe ser mayor que cero.")
        return numero_cuotas

    def clean(self):
        cleaned_data = super().clean()
        empleado = cleaned_data.get("empleado")
        tipo_prestamo = cleaned_data.get("tipo_prestamo")
        monto = cleaned_data.get("monto")
        numero_cuotas = cleaned_data.get("numero_cuotas")

        if empleado and tipo_prestamo and monto and numero_cuotas:
            prestamo_temp = Prestamo(
                empleado=empleado,
                tipo_prestamo=tipo_prestamo,
                monto=monto,
                numero_cuotas=numero_cuotas,
            )
            prestamo_temp.interes = prestamo_temp.calcular_interes()
            prestamo_temp.monto_pagar = prestamo_temp.calcular_monto_pagar()
            valor_cuota = prestamo_temp.calcular_valor_cuota()

            if valor_cuota > empleado.sueldo:
                raise forms.ValidationError(
                    f"El valor de la cuota (${valor_cuota}) no puede ser mayor "
                    f"que el sueldo del empleado (${empleado.sueldo})."
                )

        return cleaned_data
