import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from billing.models import Invoice
import cobros.models
from cobros.models import CobroFactura
from datetime import date

# Verificación 1: ¿de qué archivo se está importando el módulo?
print("ARCHIVO:", cobros.models.__file__)

# Verificación 2: ¿el método save() en memoria tiene tus prints?
import inspect
print("CÓDIGO DE save():")
print(inspect.getsource(CobroFactura.save))

factura = Invoice.objects.get(pk=1)
print("ANTES:", factura.saldo, factura.estado)

CobroFactura.objects.create(factura=factura, fecha=date.today(), valor=10, observacion="prueba script 2")

factura.refresh_from_db()
print("DESPUÉS:", factura.saldo, factura.estado)