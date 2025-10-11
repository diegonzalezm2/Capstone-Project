from django.db import models

class Persona(models.Model):
    id_persona   = models.AutoField(primary_key=True)
    run          = models.CharField(max_length=20, unique=True)        # RUT / RUN
    nombres      = models.CharField(max_length=100)
    apellidos    = models.CharField(max_length=100)
    fecha_nac    = models.DateField(null=True, blank=True)
    sexo         = models.CharField(max_length=10, null=True, blank=True)
    nro_documento = models.CharField(max_length=50, null=True, blank=True)
    is_inside    = models.BooleanField(default=False)

    class Meta:
        db_table = 'persona'
        managed = False

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.run})"
