# Create your views here.
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth import login
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.decorators import method_decorator
from .models import *
from purchasing.models import Purchase
from .forms import SignUpForm, BrandForm, InvoiceForm, InvoiceDetailFormSet, ProductForm, CustomerForm
from decimal import Decimal
from shared.mixins import StaffRequiredMixin, ExportMixin, GroupRequiredMixin
from shared.decorators import audit_action, group_required

# === REGISTRO ===
class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('billing:brand_list')
    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

# === HOME / BRAND (FBV) ===
@login_required
def home(request):
    """Vista principal del sistema. Muestra resumen general."""
    context = {
        'total_brands': Brand.objects.count(),
        'total_products': Product.objects.count(),
        'total_customers': Customer.objects.count(),
        'total_invoices': Invoice.objects.count(),
        'total_purchases': Purchase.objects.count(),
        'recent_invoices': Invoice.objects.all()[:5],
        'recent_purchases': Purchase.objects.select_related('supplier').all()[:5],
        'low_stock': Product.objects.filter(stock__lte=5, is_active=True),
    }
    return render(request, 'billing/home.html', context)


@method_decorator(audit_action('LIST_BRANDS'), name='dispatch')
class BrandListView(LoginRequiredMixin,ExportMixin,GroupRequiredMixin, ListView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Brand
    template_name = 'billing/brand_list.html'
    context_object_name = 'items'
    paginate_by = 10
    export_filename = 'marcas'
    export_fields = [
        ('id', 'ID'),
        ('name', 'Nombre de la Marca'),
        ('description', 'Descripción'),
        ('is_active', 'Estado')
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.GET
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        filter_keys = ['name', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('CREATE_BRAND')
def brand_create(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Marca Creada!')
            return redirect('billing:brand_list')
    else:
        form = BrandForm()
    return render(request, 'billing/brand_form.html', {'form': form, 'title': 'Crear Marca'})


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('UPDATE_BRAND')
def brand_update(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        form = BrandForm(request.POST, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, 'Marca Actualizada!')
            return redirect('billing:brand_list')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'billing/brand_form.html', {'form': form, 'title': 'Editar Marca'})


@login_required
@group_required('Administrador', 'Analista de Compras')
@audit_action('DELETE_BRAND')
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        brand.delete()
        messages.success(request, 'Marca Eliminada!')
        return redirect('billing:brand_list')
    return render(request, 'billing/brand_confirm_delete.html', {'object': brand})


@method_decorator(audit_action('LIST_INVOICES'), name='dispatch')
class InvoiceListView(LoginRequiredMixin,ExportMixin, GroupRequiredMixin, ListView):
    """Lista todas las facturas con sus totales."""
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'items'
    paginate_by = 10
    export_filename = 'facturas'
    export_fields = [
        ('id', 'ID'),
        ('customer.full_name', 'Cliente'),
        ('invoice_date', 'Fecha de Factura'),
        ('subtotal', 'Subtotal'),
        ('tax', 'Impuesto'),
        ('total', 'Total'),
        ('is_active', 'Estado')
    ]

    def get_queryset(self):
        qs = super().get_queryset().select_related('customer')
        p = self.request.GET
        if p.get('dni'):
            qs = qs.filter(customer__dni=p['dni'])
        if p.get('customer_name'):
            qs = qs.filter(Q(customer__first_name__icontains=p['customer_name']) | Q(customer__last_name__icontains=p['customer_name']))
        if p.get('total_min'):
            try:
                qs = qs.filter(total__gte=Decimal(p['total_min']))
            except Exception:
                pass
        if p.get('total_max'):
            try:
                qs = qs.filter(total__lte=Decimal(p['total_max']))
            except Exception:
                pass
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        filter_keys = ['dni', 'customer_name', 'total_min', 'total_max', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


@method_decorator(audit_action('CREATE_INVOICE'), name='dispatch')
class InvoiceCreateView(LoginRequiredMixin, GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    form_class = InvoiceForm
    template_name = 'billing/invoice_form.html'
    success_url = reverse_lazy('billing:invoice_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = InvoiceDetailFormSet(self.request.POST)
        else:
            ctx['formset'] = InvoiceDetailFormSet()
        
        # Serialize active products to JSON for client-side calculations
        products_qs = Product.objects.filter(is_active=True).select_related('brand')
        products_data = [
            {
                'id': p.id,
                'name': f"{p.name} ({p.brand.name})",
                'unit_price': float(p.unit_price),
                'stock': p.stock
            }
            for p in products_qs
        ]
        ctx['products_json'] = json.dumps(products_data, cls=DjangoJSONEncoder)
        ctx['title'] = 'Crear Factura'
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardamos la cabecera
                    self.object = form.save(commit=False)
                    self.object.save()

                    # Guardamos los detalles
                    formset.instance = self.object
                    formset.save()

                    # Recalculamos los totales de la factura
                    subtotal = sum(d.subtotal for d in self.object.details.all())
                    self.object.subtotal = subtotal
                    self.object.tax = subtotal * Decimal('0.15') # IVA 15%
                    self.object.total = self.object.subtotal + self.object.tax
                    self.object.save()

                messages.success(self.request, f'Factura #{self.object.id} creada correctamente! Total: ${self.object.total}')
                return redirect(self.get_success_url())
            except Exception as e:
                form.add_error(None, f"Error al guardar la factura: {str(e)}")
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


@method_decorator(audit_action('UPDATE_INVOICE'), name='dispatch')
class InvoiceUpdateView(LoginRequiredMixin, GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    form_class = InvoiceForm
    template_name = 'billing/invoice_form.html'
    success_url = reverse_lazy('billing:invoice_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = InvoiceDetailFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = InvoiceDetailFormSet(instance=self.object)
        
        # Serialize active products to JSON for client-side calculations
        products_qs = Product.objects.filter(is_active=True).select_related('brand')
        products_data = [
            {
                'id': p.id,
                'name': f"{p.name} ({p.brand.name})",
                'unit_price': float(p.unit_price),
                'stock': p.stock
            }
            for p in products_qs
        ]
        # Include inactive products if they are already in the invoice details
        existing_product_ids = set(self.object.details.values_list('product_id', flat=True))
        active_product_ids = set(p['id'] for p in products_data)
        missing_ids = existing_product_ids - active_product_ids
        if missing_ids:
            missing_products = Product.objects.filter(id__in=missing_ids).select_related('brand')
            for p in missing_products:
                products_data.append({
                    'id': p.id,
                    'name': f"{p.name} ({p.brand.name}) [Inactivo]",
                    'unit_price': float(p.unit_price),
                    'stock': p.stock
                })
        
        ctx['products_json'] = json.dumps(products_data, cls=DjangoJSONEncoder)
        ctx['title'] = 'Editar Factura'
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        if formset.is_valid():
            try:
                with transaction.atomic():
                    # Guardamos la cabecera
                    self.object = form.save()

                    # Guardamos los detalles
                    formset.save()

                    # Recalculamos los totales de la factura
                    subtotal = sum(d.subtotal for d in self.object.details.all())
                    self.object.subtotal = subtotal
                    self.object.tax = subtotal * Decimal('0.15') # IVA 15%
                    self.object.total = self.object.subtotal + self.object.tax
                    self.object.save()

                messages.success(self.request, f'Factura #{self.object.id} actualizada correctamente! Total: ${self.object.total}')
                return redirect(self.get_success_url())
            except Exception as e:
                form.add_error(None, f"Error al guardar la factura: {str(e)}")
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


@method_decorator(audit_action('DETAIL_INVOICE'), name='dispatch')
class InvoiceDetailView(LoginRequiredMixin, GroupRequiredMixin, DetailView):
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return super().get_queryset().select_related('customer').prefetch_related('details__product')


@method_decorator(audit_action('DELETE_INVOICE'), name='dispatch')
class InvoiceDeleteView(LoginRequiredMixin, GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador', 'Vendedor']
    model = Invoice
    template_name = 'billing/invoice_confirm_delete.html'
    success_url = reverse_lazy('billing:invoice_list')
    staff_redirect_url = '/invoices/'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        invoice_id = self.object.id
        success_url = self.get_success_url()
        self.object.delete()
        messages.success(request, f'Factura #{invoice_id} eliminada correctamente!')
        return redirect(success_url)


# === PRODUCTGROUP (CBV) ===
class ProductGroupListView(LoginRequiredMixin,GroupRequiredMixin, ExportMixin, ListView):
    group_required = ['Administrador', 'Analista de Compras']
    model = ProductGroup
    template_name = 'billing/productgroup_list.html'
    context_object_name = 'items'
    paginate_by = 10
    export_filename = 'grupos'
    export_fields = [
        ('id', 'ID'),
        ('name', 'Nombre del Grupo'),
        ('is_active', 'Estado')
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.GET
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        filter_keys = ['name', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx

class ProductGroupCreateView(LoginRequiredMixin,GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = ProductGroup; fields = ['name','is_active']; template_name = 'billing/productgroup_form.html'; success_url = reverse_lazy('billing:productgroup_list')
class ProductGroupUpdateView(LoginRequiredMixin,GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = ProductGroup; fields = ['name','is_active']; template_name = 'billing/productgroup_form.html'; success_url = reverse_lazy('billing:productgroup_list')
class ProductDeleteView(LoginRequiredMixin,GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Product; template_name = 'billing/product_confirm_delete.html'; success_url = reverse_lazy('billing:product_list'); staff_redirect_url = '/products/'


# === SUPPLIER (CBV) ===
class SupplierListView(LoginRequiredMixin,GroupRequiredMixin, ExportMixin, ListView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Supplier
    template_name = 'billing/supplier_list.html'
    context_object_name = 'items'
    paginate_by = 10
    export_filename = 'proveedores'
    export_fields = [
        ('id', 'ID'),
        ('name', 'Nombre de Empresa'),
        ('contact_name', 'Nombre de Contacto'),
        ('email', 'Correo'),
        ('phone', 'Teléfono'),
        ('address', 'Dirección'),
        ('is_active', 'Estado')
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.GET
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        if p.get('contact_name'):
            qs = qs.filter(contact_name__icontains=p['contact_name'])
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        filter_keys = ['name', 'contact_name', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx

class SupplierCreateView(LoginRequiredMixin,GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Supplier; fields = ['name','contact_name','email','phone','address','is_active']; template_name = 'billing/supplier_form.html'; success_url = reverse_lazy('billing:supplier_list')
class SupplierUpdateView(LoginRequiredMixin,GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Supplier; fields = ['name','contact_name','email','phone','address','is_active']; template_name = 'billing/supplier_form.html'; success_url = reverse_lazy('billing:supplier_list')
class SupplierDeleteView(LoginRequiredMixin,GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Supplier; template_name = 'billing/supplier_confirm_delete.html'; success_url = reverse_lazy('billing:supplier_list'); staff_redirect_url = '/suppliers/'


# === PRODUCT (CBV con búsqueda y pagineo) ===
class ProductListView(LoginRequiredMixin,GroupRequiredMixin, ExportMixin, ListView):
    group_required = ['Administrador', 'Analista de Compras']
    export_filename = 'productos'
    export_fields = [
        ('id', 'ID'),
        ('name', 'Nombre del Producto'),
        ('description', 'Descripción'),
        ('brand.name', 'Marca'),
        ('group.name', 'Grupo'),
        ('unit_price', 'Precio'),
        ('stock', 'Stock'),
        ('balance', 'Balance'),
        ('suppliers', 'Proveedores'),
        ('is_active', 'Estado')
    ]
    """
    Lista de productos con filtros individuales por campo y pagineo.

    Filtros disponibles (GET params):
      - name          : texto libre → icontains sobre name
      - description   : texto libre → icontains sobre description
      - brand         : id (int)    → FK exacta
      - group         : id (int)    → FK exacta
      - supplier      : id (int)    → M2M exacta
      - price_min     : decimal     → unit_price >=
      - price_max     : decimal     → unit_price <=
      - stock_min     : int         → stock >=
      - stock_max     : int         → stock <=
      - is_active     : 'true'/'false'/''/None → BooleanField
    """
    model = Product
    template_name = 'billing/product_list.html'
    context_object_name = 'items'
    paginate_by = 10

    def get_queryset(self):
        qs = (
            Product.objects
            .select_related('brand', 'group')
            .prefetch_related('suppliers')
        )
        p = self.request.GET

        # Campos de texto
        if p.get('name'):
            qs = qs.filter(name__icontains=p['name'])
        if p.get('description'):
            qs = qs.filter(description__icontains=p['description'])

        # FK → select
        if p.get('brand'):
            qs = qs.filter(brand_id=p['brand'])
        if p.get('group'):
            qs = qs.filter(group_id=p['group'])

        # M2M → select
        if p.get('supplier'):
            qs = qs.filter(suppliers__id=p['supplier'])

        # Rango de precio
        if p.get('price_min'):
            try:
                qs = qs.filter(unit_price__gte=Decimal(p['price_min']))
            except Exception:
                pass
        if p.get('price_max'):
            try:
                qs = qs.filter(unit_price__lte=Decimal(p['price_max']))
            except Exception:
                pass

        # Rango de stock
        if p.get('stock_min'):
            try:
                qs = qs.filter(stock__gte=int(p['stock_min']))
            except Exception:
                pass
        if p.get('stock_max'):
            try:
                qs = qs.filter(stock__lte=int(p['stock_max']))
            except Exception:
                pass

        # Booleano is_active
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)

        return qs.distinct()

    def get_export_fields(self):
        columns = self.request.GET.getlist('columns')
        ALL_COLUMNS = [
            ('id', 'ID'),
            ('name', 'Nombre del Producto'),
            ('description', 'Descripción'),
            ('brand.name', 'Marca'),
            ('group.name', 'Grupo'),
            ('unit_price', 'Precio'),
            ('stock', 'Stock'),
            ('balance', 'Balance'),
            ('suppliers', 'Proveedores'),
            ('is_active', 'Estado')
        ]
        if not columns:
            return ALL_COLUMNS
        return [c for c in ALL_COLUMNS if c[0] in columns]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Catálogos para los selects
        ctx['brands']    = Brand.objects.filter(is_active=True).order_by('name')
        ctx['groups']    = ProductGroup.objects.filter(is_active=True).order_by('name')
        ctx['suppliers'] = Supplier.objects.filter(is_active=True).order_by('name')
        # Valores actuales del filtro (para repintar el formulario)
        ctx['filter'] = self.request.GET
        
        ALL_COLUMNS = [
            ('id', 'ID'),
            ('name', 'Nombre del Producto'),
            ('description', 'Descripción'),
            ('brand.name', 'Marca'),
            ('group.name', 'Grupo'),
            ('unit_price', 'Precio'),
            ('stock', 'Stock'),
            ('balance', 'Balance'),
            ('suppliers', 'Proveedores'),
            ('is_active', 'Estado')
        ]
        ctx['available_columns'] = ALL_COLUMNS
        columns = self.request.GET.getlist('columns')
        if not columns:
            columns = [c[0] for c in ALL_COLUMNS]
        ctx['selected_columns'] = columns

        # Calcular si hay algún filtro activo (cualquier parámetro de búsqueda no vacío)
        filter_keys = ['name', 'description', 'brand', 'group', 'supplier', 'price_min', 'price_max', 'stock_min', 'stock_max', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        
        # Cadena de query sin 'page' para que la paginación conserve los filtros
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx


class ProductCreateView(LoginRequiredMixin,GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    success_url = reverse_lazy('billing:product_list')

class ProductUpdateView(LoginRequiredMixin,GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    success_url = reverse_lazy('billing:product_list')
class ProductDetailView(LoginRequiredMixin,GroupRequiredMixin, DetailView):
    group_required = ['Administrador', 'Analista de Compras']
    model = Product
    template_name = 'billing/product_detail.html'
    context_object_name = 'product'
class ProductGroupDeleteView(LoginRequiredMixin,GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador', 'Analista de Compras']
    model = ProductGroup; template_name = 'billing/productgroup_confirm_delete.html'; success_url = reverse_lazy('billing:productgroup_list'); staff_redirect_url = '/groups/'

# === CUSTOMER (CBV) ===
class CustomerListView(LoginRequiredMixin,GroupRequiredMixin, ExportMixin, ListView):
    group_required = ['Administrador', 'Vendedor']
    model = Customer
    template_name = 'billing/customer_list.html'
    context_object_name = 'items'
    paginate_by = 10
    export_filename = 'clientes'
    export_fields = [
        ('dni', 'DNI/RUC'),
        ('first_name', 'Nombres'),
        ('last_name', 'Apellidos'),
        ('email', 'Correo'),
        ('phone', 'Teléfono'),
        ('address', 'Dirección'),
        ('is_active', 'Estado')
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.GET
        if p.get('dni'):
            qs = qs.filter(dni=p['dni'])
        if p.get('name'):
            qs = qs.filter(Q(first_name__icontains=p['name']) | Q(last_name__icontains=p['name']))
        is_active = p.get('is_active', '')
        if is_active == 'true':
            qs = qs.filter(is_active=True)
        elif is_active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter'] = self.request.GET
        filter_keys = ['dni', 'name', 'is_active']
        ctx['has_active_filters'] = any(self.request.GET.get(k) for k in filter_keys)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['query_string'] = params.urlencode()
        return ctx

class CustomerCreateView(LoginRequiredMixin,GroupRequiredMixin, CreateView):
    group_required = ['Administrador', 'Vendedor']
    model = Customer
    form_class = CustomerForm
    template_name = 'billing/customer_form.html'
    success_url = reverse_lazy('billing:customer_list')

class CustomerUpdateView(LoginRequiredMixin,GroupRequiredMixin, UpdateView):
    group_required = ['Administrador', 'Vendedor']
    model = Customer
    form_class = CustomerForm
    template_name = 'billing/customer_form.html'
    success_url = reverse_lazy('billing:customer_list')

class CustomerDetailView(LoginRequiredMixin,GroupRequiredMixin, DetailView):
    group_required = ['Administrador', 'Vendedor']
    model = Customer
    template_name = 'billing/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Trae las facturas del cliente ordenadas por fecha descendente
        ctx['invoices'] = self.object.Facturas.select_related('customer').order_by('-invoice_date')[:10]
        return ctx

class CustomerDeleteView(LoginRequiredMixin,GroupRequiredMixin, StaffRequiredMixin, DeleteView):
    group_required = ['Administrador', 'Vendedor']
    model = Customer
    template_name = 'billing/customer_confirm_delete.html'
    success_url = reverse_lazy('billing:customer_list')
    staff_redirect_url = '/customers/'