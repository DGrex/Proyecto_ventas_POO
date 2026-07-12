from django.urls import path
from . import views
app_name = 'billing'
urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    # Brand (CBV)
    path('brands/', views.BrandListView.as_view(), name='brand_list'),
    path('brands/create/', views.brand_create, name='brand_create'),
    path('brands/<int:pk>/edit/', views.brand_update, name='brand_update'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='brand_delete'),
    # ProductGroup
    path('groups/', views.ProductGroupListView.as_view(), name='productgroup_list'),
    path('groups/create/', views.ProductGroupCreateView.as_view(), name='productgroup_create'),
    path('groups/<int:pk>/edit/', views.ProductGroupUpdateView.as_view(), name='productgroup_update'),
    path('groups/<int:pk>/delete/', views.ProductGroupDeleteView.as_view(), name='productgroup_delete'),
    # Supplier
    path('suppliers/', views.SupplierListView.as_view(), name='supplier_list'),
    path('suppliers/create/', views.SupplierCreateView.as_view(), name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier_update'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier_delete'),
    # Product
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/create/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    # Customer
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('customers/<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    # Invoice (CBV)
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_update'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice_delete'),
    path('invoices/<int:pk>/comprobante/', views.invoice_comprobante_pdf, name='invoice_comprobante'),
    path('invoices/<int:pk>/voucher/', views.InvoiceDetailView.as_view(), name='invoice_detail_voucher'),
    
]