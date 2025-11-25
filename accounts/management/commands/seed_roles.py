# seed_roles.py
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction

ROLES = ["Administrador", "Jefe de seguridad", "Guardia"]

def get_Rol_model():
    """
    Busca dinámicamente el modelo Rol sin asumir app o nombre exacto del archivo.
    Cambia aquí si tu clase no se llama 'Rol' o está en otro app label.
    """
    candidates = [
        ("personas", "Rol"),
        ("accounts", "Rol"),
        ("personas", "Role"),
        ("accounts", "Role"),
    ]
    for app_label, model_name in candidates:
        try:
            Model = apps.get_model(app_label, model_name)
            if Model is not None:
                return Model
        except Exception:
            pass
    raise LookupError(
        "No se encontró el modelo 'Rol'. Verifica en qué app/clase está definido "
        "(por ej. personas.models.Rol) y ajusta la lista 'candidates' arriba."
    )

class Command(BaseCommand):
    help = "Crea los roles base en la tabla 'rol' (si no existen)."

    @transaction.atomic
    def handle(self, *args, **options):
        Rol = get_Rol_model()  # <- obtenemos el modelo real
        creados = 0
        for nombre in ROLES:
            obj, was_created = Rol.objects.get_or_create(nombre_rol=nombre)
            if was_created:
                creados += 1
                self.stdout.write(self.style.SUCCESS(f"Creado: {obj.nombre_rol}"))
            else:
                self.stdout.write(f"Ya existe: {obj.nombre_rol}")
        self.stdout.write(self.style.SUCCESS(f"Listo. Roles nuevos: {creados}"))
