from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Brand, ProductGroup, Supplier, Product, Customer, Invoice, InvoiceDetail
from .forms import ProductForm, CustomerForm


class ProductListFilterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client = Client()
        self.client.login(username='testuser', password='password123')
        
        # Crear datos de prueba relacionales para verificar el mixin genérico
        self.brand = Brand.objects.create(name="Marca de Prueba")
        self.group = ProductGroup.objects.create(name="Grupo de Prueba")
        self.supplier = Supplier.objects.create(name="Proveedor de Prueba")
        
        self.product = Product.objects.create(
            name="Producto de Prueba",
            description="Descripción de prueba con caracteres especiales & algo más",
            brand=self.brand,
            group=self.group,
            unit_price=15.99,
            stock=50,
            is_active=True
        )
        self.product.suppliers.add(self.supplier)

        # Crear cliente con DNI ecuatoriano válido de prueba
        self.customer = Customer.objects.create(
            dni="1710403333",
            first_name="Juan",
            last_name="Perez",
            email="juan@perez.com",
            phone="0999999999",
            address="Quito",
            is_active=True
        )
        
        # Crear factura de prueba
        self.invoice = Invoice.objects.create(
            customer=self.customer,
            subtotal=100.00,
            tax=15.00,
            total=115.00,
            is_active=True
        )
        
    def test_product_balance_property(self):
        # 15.99 unit price * 50 stock = 799.50
        self.assertEqual(self.product.balance, 799.50)
        
    def test_product_photo_properties(self):
        # Cuando el producto no tiene imagen, debe devolver la ruta de la imagen por defecto
        self.assertFalse(self.product.image)
        self.assertEqual(self.product.photo, self.product.image)
        self.assertEqual(self.product.get_photo_url(), '/static/billing/img/no-photo.svg')

        # Cuando el producto tiene imagen, debe devolver la URL de la imagen
        from django.core.files.uploadedfile import SimpleUploadedFile
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
        self.product.image = SimpleUploadedFile("product_photo.gif", image_content, content_type="image/gif")
        self.product.save()

        self.assertTrue(self.product.image)
        self.assertEqual(self.product.photo, self.product.image)
        self.assertEqual(self.product.get_photo_url(), self.product.image.url)

    def test_product_list_renders_with_collapsible_filter(self):
        response = self.client.get(reverse('billing:product_list'))
        self.assertEqual(response.status_code, 200)
        # Verificar que la estructura de colapsable de Bootstrap está presente
        self.assertContains(response, 'id="filterCollapse"')
        self.assertContains(response, 'data-bs-toggle="collapse"')
        # Verificar que el panel inicia colapsado (no contiene la clase "show" de Bootstrap)
        self.assertNotContains(response, 'class="collapse show"')
        
    def test_product_list_renders_expanded_when_filters_active(self):
        # Aplicar un filtro de búsqueda simulado en la URL
        response = self.client.get(reverse('billing:product_list') + '?name=test')
        self.assertEqual(response.status_code, 200)
        # Verificar que el panel se inicia expandido si hay filtros activos (contiene "collapse show")
        self.assertContains(response, 'collapse show')
        # Verificar que se muestra el badge de Filtros Activos
        self.assertContains(response, 'Filtros Activos')

    # --- PRUEBAS DE EXPORTACIÓN: PRODUCTOS ---
    def test_export_products_to_excel(self):
        response = self.client.get(reverse('billing:product_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="productos_'))

    def test_export_products_to_pdf(self):
        response = self.client.get(reverse('billing:product_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="productos_'))

    # --- PRUEBAS DE EXPORTACIÓN: MARCAS ---
    def test_export_brands_to_excel(self):
        response = self.client.get(reverse('billing:brand_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="marcas_'))

    def test_export_brands_to_pdf(self):
        response = self.client.get(reverse('billing:brand_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="marcas_'))

    # --- PRUEBAS DE EXPORTACIÓN: GRUPOS ---
    def test_export_groups_to_excel(self):
        response = self.client.get(reverse('billing:productgroup_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="grupos_'))

    def test_export_groups_to_pdf(self):
        response = self.client.get(reverse('billing:productgroup_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="grupos_'))

    # --- PRUEBAS DE EXPORTACIÓN: PROVEEDORES ---
    def test_export_suppliers_to_excel(self):
        response = self.client.get(reverse('billing:supplier_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="proveedores_'))

    def test_export_suppliers_to_pdf(self):
        response = self.client.get(reverse('billing:supplier_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="proveedores_'))

    # --- PRUEBAS DE EXPORTACIÓN: CLIENTES ---
    def test_export_customers_to_excel(self):
        response = self.client.get(reverse('billing:customer_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="clientes_'))

    def test_export_customers_to_pdf(self):
        response = self.client.get(reverse('billing:customer_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="clientes_'))

    # --- PRUEBAS DE EXPORTACIÓN: FACTURAS ---
    def test_export_invoices_to_excel(self):
        response = self.client.get(reverse('billing:invoice_list') + '?export=excel')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="facturas_'))

    def test_export_invoices_to_pdf(self):
        response = self.client.get(reverse('billing:invoice_list') + '?export=pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="facturas_'))

    # --- PRUEBA DE DETALLE DE PRODUCTO ---
    def test_product_detail_view(self):
        response = self.client.get(reverse('billing:product_detail', kwargs={'pk': self.product.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        self.assertContains(response, self.product.brand.name)
        self.assertContains(response, self.product.group.name)
        # En la localización es-ec, 15.99 se renderiza con coma: 15,99
        self.assertContains(response, "15,99")

class ProductFormTest(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Marca Test Form")
        self.group = ProductGroup.objects.create(name="Grupo Test Form")
        self.supplier = Supplier.objects.create(name="Proveedor Test Form")

    def test_form_validation_price_positive(self):
        form_data = {
            'name': 'Producto Test Form',
            'description': 'Descripción',
            'brand': self.brand.id,
            'group': self.group.id,
            'suppliers': [self.supplier.id],
            'unit_price': 10.99,
            'stock': 25,
            'is_active': True
        }
        form = ProductForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_validation_price_zero(self):
        form_data = {
            'name': 'Producto Test Form',
            'description': 'Descripción',
            'brand': self.brand.id,
            'group': self.group.id,
            'suppliers': [self.supplier.id],
            'unit_price': 0,
            'stock': 25,
            'is_active': True
        }
        form = ProductForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('unit_price', form.errors)
        self.assertEqual(form.errors['unit_price'][0], "El precio unitario debe ser mayor que cero.")

    def test_form_validation_price_negative(self):
        form_data = {
            'name': 'Producto Test Form',
            'description': 'Descripción',
            'brand': self.brand.id,
            'group': self.group.id,
            'suppliers': [self.supplier.id],
            'unit_price': -5.50,
            'stock': 25,
            'is_active': True
        }
        form = ProductForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('unit_price', form.errors)
        self.assertEqual(form.errors['unit_price'][0], "El precio unitario debe ser mayor que cero.")

    def test_form_with_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
        simulated_image = SimpleUploadedFile("test_image.gif", image_content, content_type="image/gif")
        
        form_data = {
            'name': 'Producto con Imagen',
            'description': 'Descripción',
            'brand': self.brand.id,
            'group': self.group.id,
            'suppliers': [self.supplier.id],
            'unit_price': 15.00,
            'stock': 10,
            'is_active': True
        }
        form_files = {
            'image': simulated_image
        }
        form = ProductForm(data=form_data, files=form_files)
        self.assertTrue(form.is_valid(), form.errors.as_data())
        product = form.save()
        self.assertTrue(product.image.name.startswith('products/test_image'))

    def test_view_create_product_with_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client = Client()
        user = User.objects.create_user(username='testviewuser', password='password123')
        self.client.login(username='testviewuser', password='password123')
        
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
        simulated_image = SimpleUploadedFile("view_image.gif", image_content, content_type="image/gif")
        
        post_data = {
            'name': 'Producto de Vista con Imagen',
            'description': 'Descripción',
            'brand': self.brand.id,
            'group': self.group.id,
            'suppliers': [self.supplier.id],
            'unit_price': 25.50,
            'stock': 100,
            'is_active': True,
            'image': simulated_image
        }
        response = self.client.post(reverse('billing:product_create'), data=post_data)
        self.assertEqual(response.status_code, 302)
        
        product = Product.objects.get(name='Producto de Vista con Imagen')
        self.assertTrue(product.image.name.startswith('products/view_image'))


class StockUpdateTest(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Marca Stock")
        self.group = ProductGroup.objects.create(name="Grupo Stock")
        self.product = Product.objects.create(
            name="Producto Stock",
            brand=self.brand,
            group=self.group,
            unit_price=10.00,
            stock=100,
            is_active=True
        )
        self.customer = Customer.objects.create(
            dni="1710403333",
            first_name="Stock",
            last_name="User",
            email="stock@user.com",
            is_active=True
        )
        self.invoice = Invoice.objects.create(
            customer=self.customer,
            is_active=True
        )

    def test_stock_decreases_on_detail_create(self):
        # Crear un InvoiceDetail
        detail = InvoiceDetail.objects.create(
            invoice=self.invoice,
            product=self.product,
            quantity=5,
            unit_price=10.00
        )
        # Recargar producto de la base de datos
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 95)

    def test_stock_adjusts_on_detail_update(self):
        detail = InvoiceDetail.objects.create(
            invoice=self.invoice,
            product=self.product,
            quantity=5,
            unit_price=10.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 95)

        # Modificar cantidad
        detail.quantity = 12
        detail.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 88) # 100 - 12 = 88

    def test_stock_restores_on_detail_delete(self):
        detail = InvoiceDetail.objects.create(
            invoice=self.invoice,
            product=self.product,
            quantity=5,
            unit_price=10.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 95)

        # Eliminar el detalle
        detail.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

    def test_stock_restores_on_invoice_cascade_delete(self):
        InvoiceDetail.objects.create(
            invoice=self.invoice,
            product=self.product,
            quantity=8,
            unit_price=10.00
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 92)

        # Eliminar la factura (debe eliminar el detalle en cascada y restaurar el stock)
        self.invoice.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)


class CustomerFormTest(TestCase):
    def test_form_validation_valid_data(self):
        form_data = {
            'dni': '1710403336',  # Valid Ecuadorian DNI
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'email': 'juan@perez.com',
            'phone': '0999999999',
            'address': 'Quito, Ecuador',
            'is_active': True
        }
        form = CustomerForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors.as_data())

    def test_form_validation_invalid_dni(self):
        form_data = {
            'dni': '1710403333',  # Invalid verifier digit
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'is_active': True
        }
        form = CustomerForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('dni', form.errors)

    def test_form_validation_missing_required(self):
        form_data = {
            'dni': '1710403336',
            'first_name': '',
            'last_name': 'Pérez',
            'is_active': True
        }
        form = CustomerForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)


class CustomerViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customeruser', password='password123')
        self.client = Client()
        self.client.login(username='customeruser', password='password123')
        # Use valid DNI to prevent any issues with other logic
        self.customer = Customer.objects.create(
            dni='1710403336',
            first_name='Juan',
            last_name='Pérez',
            email='juan@perez.com',
            phone='0999999999',
            address='Quito',
            is_active=True
        )

    def test_customer_list_view(self):
        response = self.client.get(reverse('billing:customer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.first_name)
        self.assertContains(response, self.customer.dni)

    def test_customer_detail_view(self):
        Invoice.objects.create(
            customer=self.customer,
            subtotal=10.00,
            tax=1.50,
            total=11.50,
            is_active=True
        )
        response = self.client.get(reverse('billing:customer_detail', kwargs={'pk': self.customer.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.first_name)
        self.assertContains(response, self.customer.last_name)
        self.assertContains(response, self.customer.dni)
        # In es-ec format, decimal separators are commas
        self.assertContains(response, "11,50")

    def test_customer_create_view_get(self):
        response = self.client.get(reverse('billing:customer_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DNI / RUC')

    def test_customer_create_view_post(self):
        post_data = {
            'dni': '1710403344',  # Another valid Ecuadorian DNI
            'first_name': 'María',
            'last_name': 'Gómez',
            'email': 'maria@gomez.com',
            'phone': '0987654321',
            'address': 'Guayaquil',
            'is_active': True
        }
        response = self.client.post(reverse('billing:customer_create'), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(dni='1710403344').exists())

    def test_customer_update_view_get(self):
        response = self.client.get(reverse('billing:customer_update', kwargs={'pk': self.customer.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer.first_name)

    def test_customer_update_view_post(self):
        post_data = {
            'dni': self.customer.dni,
            'first_name': 'Juan Carlos',
            'last_name': 'Pérez Modificado',
            'email': 'juan@nuevo.com',
            'phone': '0999999999',
            'address': 'Quito Nuevo',
            'is_active': False
        }
        response = self.client.post(reverse('billing:customer_update', kwargs={'pk': self.customer.pk}), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Juan Carlos')
        self.assertEqual(self.customer.last_name, 'Pérez Modificado')
        self.assertFalse(self.customer.is_active)

    def test_customer_delete_view_post_by_non_staff(self):
        # By default, a normal user is not staff. The view redirects if the user is not staff.
        response = self.client.post(reverse('billing:customer_delete', kwargs={'pk': self.customer.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())

    def test_customer_delete_view_post_by_staff(self):
        self.user = User.objects.get(username='customeruser')
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(reverse('billing:customer_delete', kwargs={'pk': self.customer.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())


