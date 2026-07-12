from django.urls import path
from . import views

app_name = 'pagos'

urlpatterns = [
    path('', views.compra_pendiente_list, name='compra_pendiente_list'),
    path('compra/<int:compra_id>/pagar/', views.pago_create, name='pago_create'),
    path('compra/<int:compra_id>/historial/', views.pago_list, name='pago_list'),
    path('pago/<int:pk>/editar/', views.pago_update, name='pago_update'),
    path('pago/<int:pk>/eliminar/', views.pago_delete, name='pago_delete'),
]