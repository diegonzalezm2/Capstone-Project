# accounts/management/commands/bootstrap_roles_perms.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# === Ajusta aquí si tus nombres de app/modelo son distintos ===
# app_label = nombre de la app; model_name = Nombre de la clase del modelo
MODELOS_PERMISOS = [
    ("visitas", "Visita"),
    ("personas", "Persona"),
    ("lugares", "Lugar"),
]

ROL_DEFINICION = {
    # Puede ver todo el dashboard, exportar, administrar
    "Administrador": {
        "perms": ["add", "change", "delete", "view"],
        "models": MODELOS_PERMISOS,
    },
    # Puede ver dashboard y exportar, gestionar visitas (pero no borrar)
    "Jefe de seguridad": {
        "perms": ["add", "change", "view"],
        "models": MODELOS_PERMISOS,
    },
    # Puede registrar visitas (crear/editar), ver, NO borra ni exporta
    "Guardia": {
        "perms": ["add", "change", "view"],
        "models": [
            ("visitas", "Visita"),  # solo Visita para guardias
        ],
    },
}


class Command(BaseCommand):
    help = "Crea/actualiza los Grupos (roles) y asigna permisos por modelo."

    def handle(self, *args, **options):
        total_roles = 0
        for group_name, conf in ROL_DEFINICION.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            asignados = 0

            for app_label, model_name in conf["models"]:
                # ContentType.model es en minúsculas (nombre del modelo)
                ct = ContentType.objects.filter(
                    app_label=app_label, model=model_name.lower()
                ).first()
                if not ct:
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{group_name}] No existe ContentType para {app_label}.{model_name}. "
                            f"Ejecuta migraciones si es necesario."
                        )
                    )
                    continue

                for pfx in conf["perms"]:
                    # Codenames estándar de Django: add_modelo, change_modelo, delete_modelo, view_modelo
                    codename = f"{pfx}_{model_name.lower()}"
                    perm = Permission.objects.filter(
                        content_type=ct, codename=codename
                    ).first()
                    if not perm:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{group_name}] Permiso no encontrado: {codename}"
                            )
                        )
                        continue
                    group.permissions.add(perm)
                    asignados += 1

            total_roles += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Grupo '{group_name}' sincronizado. Permisos asignados: {asignados}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"Listo. Grupos/roles procesados: {total_roles}.")
        )
