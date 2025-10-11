from django.db import models

class Rol(models.Model):
    id_rol    = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=100)

    class Meta:
        db_table = 'rol'
        managed = False

    def __str__(self):
        return self.nombre_rol


class Usuario(models.Model):
    id_usuario   = models.AutoField(primary_key=True)
    nombre       = models.CharField(max_length=100)
    email        = models.CharField(max_length=100, unique=True)
    hash_password = models.CharField(max_length=255)
    rol          = models.ForeignKey(Rol, models.DO_NOTHING, db_column='rol_id')
    activo       = models.BooleanField(default=True)

    class Meta:
        db_table = 'usuario'
        managed = False

    def __str__(self):
        return self.nombre
