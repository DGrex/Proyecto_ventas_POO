from django.urls import path
from . import views

app_name = 'cobros'

urlpatterns = [
    path('', views.FacturaPendienteListView.as_view(), name='factura_pendiente_list'),
    path('factura/<int:factura_id>/pagar/', views.CobroCreateView.as_view(), name='cobro_create'),
    path('factura/<int:factura_id>/historial/', views.CobroListView.as_view(), name='cobro_list'),
    path('pago/<int:pk>/editar/', views.CobroUpdateView.as_view(), name='cobro_update'),
    path('pago/<int:pk>/eliminar/', views.CobroDeleteView.as_view(), name='cobro_delete'),
]