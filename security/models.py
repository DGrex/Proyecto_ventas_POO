from django.db import models


class ExportPermission(models.Model):
    """
    Modelo sin tabla real (managed=False): solo existe para alojar los permisos
    globales de exportación de reportes, ya que Django exige un modelo/content-type
    para poder crear y asignar permisos a los roles.
    """
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('export_pdf', 'Puede exportar reportes a PDF'),
            ('export_excel', 'Puede exportar reportes a Excel'),
        ]
