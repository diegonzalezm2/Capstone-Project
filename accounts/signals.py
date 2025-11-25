# accounts/signals.py
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth.models import Group
from django.apps import apps

def get_model(app_model):
    app_label, model_name = app_model.split(".")
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

Usuario = get_model("personas.Usuario") or get_model("accounts.Usuario")

ROLE_GROUP_MAP = {
    "Administrador": "Administrador",
    "Jefe de seguridad": "Jefe de seguridad",
    "Guardia": "Guardia",
}

def _get_usuario_by_email(user):
    if not (Usuario and user and user.email):
        return None
    return Usuario.objects.select_related("rol").filter(email__iexact=user.email).first()

def _sync_user_groups_from_db_role(user):
    uapp = _get_usuario_by_email(user)
    role_name = getattr(getattr(uapp, "rol", None), "nombre_rol", None)

    managed = set(ROLE_GROUP_MAP.values())
    curr = set(user.groups.values_list("name", flat=True))
    to_remove = curr.intersection(managed)
    if to_remove:
        user.groups.remove(*Group.objects.filter(name__in=to_remove))

    wanted = ROLE_GROUP_MAP.get(role_name)
    if wanted:
        grp, _ = Group.objects.get_or_create(name=wanted)
        user.groups.add(grp)

@receiver(post_save, sender=apps.get_model("auth", "User"))
def sync_groups_on_user_save(sender, instance, **kwargs):
    _sync_user_groups_from_db_role(instance)

@receiver(user_logged_in)
def sync_groups_on_login(sender, user, request, **kwargs):
    _sync_user_groups_from_db_role(user)
