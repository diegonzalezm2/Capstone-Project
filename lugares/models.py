from django.db import models

class Lugar(models.Model):
    id_lugar     = models.AutoField(primary_key=True)
    nombre_lugar = models.CharField(max_length=100)

    class Meta:
        db_table = 'lugar'
        managed = False

    def __str__(self):
        return self.nombre_lugar
