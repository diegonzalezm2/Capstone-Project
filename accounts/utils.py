# accounts/utils.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.apps import apps

def get_model(app_model):
    app_label, model_name = app_model.split(".")
    try:
        return apps.get_model(app_label, model_name)
    except Exception:
        return None

Usuario = get_model("personas.Usuario") or get_model("accounts.Usuario")

def _get_usuario_by_email(user):
    if not (Usuario and user and user.email):
        return None
    return Usuario.objects.select_related("rol").filter(email__iexact=user.email).first()

def db_role_required(*role_names):
    """
    Restringe acceso comparando el rol de tu tabla 'usuario' (por email).
    Ej.: @db_role_required("Administrador", "Jefe de seguridad")
    """
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            uapp = _get_usuario_by_email(request.user)
            nombre = getattr(getattr(uapp, "rol", None), "nombre_rol", None)
            if nombre in role_names:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped
    return decorator
