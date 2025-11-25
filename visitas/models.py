# visitas/models.py
from django.db import models
from personas.models import Persona
from lugares.models import Lugar
from accounts.models import Usuario

class Visita(models.Model):
    id_visita = models.AutoField(primary_key=True)
    persona   = models.ForeignKey(Persona, models.DO_NOTHING, db_column='persona_id')
    entrada_at = models.DateTimeField(null=True, blank=True)
    salida_at  = models.DateTimeField(null=True, blank=True)

    # NOTA: estos FKs apuntan a la tabla 'usuario' (accounts.Usuario)
    operador_entrada = models.ForeignKey(
        Usuario, models.DO_NOTHING,
        db_column='operador_entrada_id',
        related_name='visitas_registradas',
        null=False, blank=False
    )
    operador_salida = models.ForeignKey(
        Usuario, models.DO_NOTHING,
        db_column='operador_salida_id',
        related_name='visitas_cerradas',
        null=True, blank=True
    )
    lugar = models.ForeignKey(Lugar, models.DO_NOTHING, db_column='lugar_id')

    class Meta:
        db_table = 'visita'
        managed = False  # mapeamos tabla existente

    def __str__(self):
        return f"Visita #{self.id_visita} - {self.persona} - {self.lugar}"
