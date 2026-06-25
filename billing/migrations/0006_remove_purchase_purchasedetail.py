from django.db import migrations


class Migration(migrations.Migration):
    """
    Elimina los modelos Purchase y PurchaseDetail que fueron añadidos
    accidentalmente a la app billing. Estos modelos ahora viven en la app
    purchasing (separada).
    """

    dependencies = [
        ('billing', '0005_purchase_purchasedetail'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PurchaseDetail',
        ),
        migrations.DeleteModel(
            name='Purchase',
        ),
    ]
