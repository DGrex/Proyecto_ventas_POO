from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import IntegrityError
from decimal import Decimal
from billing.models import Brand, ProductGroup, Supplier, Product
from .models import Purchase, PurchaseDetail


class PurchasingModelTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Marca Test Compra")
        self.group = ProductGroup.objects.create(name="Grupo Test Compra")
        self.supplier = Supplier.objects.create(name="Proveedor Test Compra")
        self.product = Product.objects.create(
            name="Producto Test Compra",
            brand=self.brand,
            group=self.group,
            unit_price=20.00,
            stock=10,
            is_active=True
        )

    def test_stock_increases_on_purchase_detail_create(self):
        # Al crear un detalle de compra, el stock debe aumentar.
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="DOC-001"
        )
        detail = PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=5,
            unit_cost=15.00
        )
        self.assertEqual(detail.subtotal, Decimal("75.00"))
        
        # Verificar que el stock del producto aumentó: 10 + 5 = 15
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

    def test_stock_adjusts_on_purchase_detail_update(self):
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="DOC-002"
        )
        detail = PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=5,
            unit_cost=15.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

        # Modificamos la cantidad a 8 (aumento de 3)
        detail.quantity = 8
        detail.save()
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 18)

        # Modificamos la cantidad a 3 (disminución de 5)
        detail.quantity = 3
        detail.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 13)

    def test_stock_restores_on_purchase_detail_delete(self):
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="DOC-003"
        )
        detail = PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=7,
            unit_cost=12.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 17)

        # Eliminamos el detalle de compra, debe restar la cantidad al stock del producto
        detail.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_stock_restores_on_purchase_cascade_delete(self):
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="DOC-004"
        )
        PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=10,
            unit_cost=10.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)

        # Eliminar la compra en cascada
        purchase.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_unique_document_number_per_supplier(self):
        # Crear la primera compra
        Purchase.objects.create(
            supplier=self.supplier,
            document_number="DUP-123"
        )
        
        # Intentar crear una segunda compra con el mismo proveedor y document_number
        with self.assertRaises(IntegrityError):
            Purchase.objects.create(
                supplier=self.supplier,
                document_number="DUP-123"
            )


class PurchasingViewsTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group
        compras_group, _ = Group.objects.get_or_create(name='Analista de Compras')
        self.user = User.objects.create_user(username='purchasinguser', password='password123')
        self.user.groups.add(compras_group)
        self.client = Client()
        self.client.login(username='purchasinguser', password='password123')

        self.brand = Brand.objects.create(name="Marca Test Vista")
        self.group = ProductGroup.objects.create(name="Grupo Test Vista")
        self.supplier = Supplier.objects.create(name="Proveedor Test Vista", is_active=True)
        self.product = Product.objects.create(
            name="Producto Test Vista",
            brand=self.brand,
            group=self.group,
            unit_price=20.00,
            stock=10,
            is_active=True
        )

        self.purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="FAC-789",
            subtotal=100.00,
            tax=15.00,
            total=115.00
        )
        self.detail = PurchaseDetail.objects.create(
            purchase=self.purchase,
            product=self.product,
            quantity=5,
            unit_cost=20.00,
            subtotal=100.00
        )

    def test_purchase_list_view(self):
        response = self.client.get(reverse('purchasing:purchase_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.supplier.name)
        self.assertContains(response, "FAC-789")
        # Promedio costo unitario
        self.assertContains(response, "20,00") # es-ec localiza 20.00 como 20,00

    def test_purchase_list_filtering(self):
        # Filtro de proveedor que coincide
        response = self.client.get(reverse('purchasing:purchase_list') + f'?supplier={self.supplier.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FAC-789")

        # Filtro de proveedor que no coincide (creamos otro proveedor)
        other_supplier = Supplier.objects.create(name="Otro Proveedor", is_active=True)
        response = self.client.get(reverse('purchasing:purchase_list') + f'?supplier={other_supplier.id}')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "FAC-789")

    def test_purchase_detail_view(self):
        response = self.client.get(reverse('purchasing:purchase_detail', kwargs={'pk': self.purchase.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.supplier.name)
        self.assertContains(response, "FAC-789")
        self.assertContains(response, self.product.name)

    def test_purchase_create_view_get(self):
        response = self.client.get(reverse('purchasing:purchase_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nº Factura Proveedor')

    def test_purchase_create_view_post(self):
        # Verificar stock inicial
        self.product.refresh_from_db()
        initial_stock = self.product.stock

        post_data = {
            'supplier': self.supplier.id,
            'document_number': 'NUEVA-111',
            # Formset management fields
            'details-TOTAL_FORMS': '1',
            'details-INITIAL_FORMS': '0',
            'details-MIN_NUM_FORMS': '0',
            'details-MAX_NUM_FORMS': '1000',
            # Detalle 0
            'details-0-product': self.product.id,
            'details-0-quantity': '4',
            'details-0-unit_cost': '12.50',
            'details-0-id': '',
        }
        response = self.client.post(reverse('purchasing:purchase_create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        # Verificar que se creó la compra
        purchase = Purchase.objects.get(document_number='NUEVA-111')
        self.assertEqual(purchase.supplier, self.supplier)
        self.assertEqual(purchase.subtotal, Decimal("50.00")) # 4 * 12.50
        self.assertEqual(purchase.tax, Decimal("7.50")) # 50 * 0.15
        self.assertEqual(purchase.total, Decimal("57.50"))

        # Verificar que se actualizó el stock: anterior + 4
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, initial_stock + 4)

    def test_purchase_update_view_post(self):
        # Crear una compra nueva para actualizar
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="UP-TEST"
        )
        detail = PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=2,
            unit_cost=10.00
        )
        self.product.refresh_from_db()
        stock_before_update = self.product.stock

        post_data = {
            'supplier': self.supplier.id,
            'document_number': 'UP-TEST-MOD',
            # Formset management fields
            'details-TOTAL_FORMS': '1',
            'details-INITIAL_FORMS': '1',
            'details-MIN_NUM_FORMS': '0',
            'details-MAX_NUM_FORMS': '1000',
            # Detalle existente 0
            'details-0-product': self.product.id,
            'details-0-quantity': '5',  # Aumentamos de 2 a 5 (+3)
            'details-0-unit_cost': '12.00',
            'details-0-id': detail.id,
        }

        response = self.client.post(reverse('purchasing:purchase_update', kwargs={'pk': purchase.pk}), data=post_data)
        self.assertEqual(response.status_code, 302)

        purchase.refresh_from_db()
        self.assertEqual(purchase.document_number, 'UP-TEST-MOD')
        self.assertEqual(purchase.subtotal, Decimal("60.00")) # 5 * 12.00

        # Verificar stock: stock_before_update + 3
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_before_update + 3)

    def test_purchase_delete_view_post(self):
        # Dar rol Administrador para permitir la eliminación
        from django.contrib.auth.models import Group
        admin_group, _ = Group.objects.get_or_create(name='Administrador')
        self.user.groups.add(admin_group)
        self.user.save()

        # Crear una compra para eliminar
        purchase = Purchase.objects.create(
            supplier=self.supplier,
            document_number="DEL-TEST"
        )
        PurchaseDetail.objects.create(
            purchase=purchase,
            product=self.product,
            quantity=6,
            unit_cost=10.00
        )
        self.product.refresh_from_db()
        stock_before_delete = self.product.stock

        # Eliminar mediante post
        response = self.client.post(reverse('purchasing:purchase_delete', kwargs={'pk': purchase.pk}))
        self.assertEqual(response.status_code, 302)

        # Verificar que ya no existe la compra
        self.assertFalse(Purchase.objects.filter(pk=purchase.pk).exists())

        # Verificar stock: disminuido en 6
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, stock_before_delete - 6)
