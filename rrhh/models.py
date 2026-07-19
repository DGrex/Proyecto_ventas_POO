import calendar
from decimal import Decimal

from django.db import models


class TipoPrestamo(models.Model):


    descripcion = models.CharField(max_length=100)

    tasa_interes = models.IntegerField(default=0)

    def __str__(self):

        return self.descripcion


class Empleado(models.Model):
    

    nombres = models.CharField(max_length=100)

    sueldo = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):

        return self.nombres


class Prestamo(models.Model):
    

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE)

    tipo_prestamo = models.ForeignKey(TipoPrestamo, on_delete=models.CASCADE)

    fecha_prestamo = models.DateField()

    monto = models.DecimalField(max_digits=10, decimal_places=2)

    interes = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    monto_pagar = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    numero_cuotas = models.PositiveIntegerField(default=1)

    saldo = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    ESTADOS = [
        ("PEND", "Pendiente"),
        ("PAG", "Pagado"),
        ("ANU", "Anulado"),
    ]

    estado = models.CharField(max_length=4, choices=ESTADOS, default="PEND")

    def __str__(self):

        return f"Préstamo #{self.pk} - {self.empleado}"

    def calcular_interes(self):

        tasa = Decimal(self.tipo_prestamo.tasa_interes)

        return (self.monto * tasa) / Decimal("100")
    
    def calcular_interesPrueba(numer):

        tasa = Decimal(number)

        return (self.monto * tasa) / Decimal("100")


    def calcular_monto_pagar(self):
    

        return self.monto + self.interes

    def calcular_valor_cuota(self):

        return (self.monto_pagar / self.numero_cuotas).quantize(Decimal("0.01"))

    def generar_prestamo(self):
  

        self.interes = self.calcular_interes()
        self.monto_pagar = self.calcular_monto_pagar()
        self.saldo = self.monto_pagar
        self.estado = "PEND"
        self.save()

        self.generar_detalle()

    @staticmethod
    def sumar_meses(fecha, meses):
  

        mes = fecha.month - 1 + meses
        anio = fecha.year + mes // 12
        mes = mes % 12 + 1
        dia = min(fecha.day, calendar.monthrange(anio, mes)[1])

        return fecha.replace(year=anio, month=mes, day=dia)

    def generar_detalle(self):

        self.detalles.all().delete()

        valor_cuota = self.calcular_valor_cuota()
        acumulado = Decimal("0.00")

        for numero in range(1, self.numero_cuotas + 1):

            fecha_vencimiento = self.sumar_meses(self.fecha_prestamo, numero)

            if numero == self.numero_cuotas:
                # La última cuota se ajusta para que la suma cuadre exacto
                valor = self.monto_pagar - acumulado
            else:
                valor = valor_cuota
                acumulado += valor

            PrestamoDetalle.objects.create(
                prestamo=self,
                numero_cuota=numero,
                fecha_vencimiento=fecha_vencimiento,
                valor_cuota=valor,
                saldo_cuota=valor,
            )

    def anular(self):
    

        self.estado = "ANU"
        self.save()




class PrestamoDetalle(models.Model):


    prestamo = models.ForeignKey(
        Prestamo, related_name="detalles", on_delete=models.CASCADE
    )

    numero_cuota = models.PositiveIntegerField()

    fecha_vencimiento = models.DateField()

    valor_cuota = models.DecimalField(max_digits=10, decimal_places=2)

    saldo_cuota = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["numero_cuota"]

    def __str__(self):

        return f"Cuota {self.numero_cuota} - Préstamo #{self.prestamo_id}"

    @property
    def pagada(self):

        return self.saldo_cuota <= 0

    def pagar(self):
    

        if self.pagada:
            return

        prestamo = self.prestamo
        prestamo.saldo -= self.saldo_cuota

        if prestamo.saldo < 0:
            prestamo.saldo = Decimal("0.00")

        self.saldo_cuota = Decimal("0.00")
        self.save()

        if prestamo.saldo == 0:
            prestamo.estado = "PAG"

        prestamo.save()
