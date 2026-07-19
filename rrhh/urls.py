from django.urls import path

from . import views

app_name = "rrhh"

urlpatterns = [
    path("", views.prestamo_list, name="prestamo_list"),
    path("crear/", views.prestamo_create, name="prestamo_create"),
    path("<int:pk>/", views.prestamo_detail, name="prestamo_detail"),
    path("<int:pk>/editar/", views.prestamo_update, name="prestamo_update"),
    path("<int:pk>/eliminar/", views.prestamo_delete, name="prestamo_delete"),
    path("<int:pk>/anular/", views.prestamo_anular, name="prestamo_anular"),
    path("cuota/<int:pk>/pagar/", views.cuota_pagar, name="cuota_pagar"),
]
