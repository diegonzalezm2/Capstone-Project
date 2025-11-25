# accounts/context_processors.py
from .helpers import get_usuario_for  # <- IMPORT CORRECTO

def ui_flags(request):
    """
    Banderas para la UI:
      - ui_is_admin: True si el rol es Administrador o Jefe de seguridad
      - ui_role_name: nombre de rol legible
    """
    is_admin = False
    role_name = ""

    if request.user.is_authenticated:
        uapp = get_usuario_for(request.user)
        if uapp and getattr(uapp, "rol", None):
            # nombre_rol o nombre, según tu modelo
            role_name = getattr(uapp.rol, "nombre_rol", "") or getattr(uapp.rol, "nombre", "")
            is_admin = role_name in ("Administrador", "Jefe de seguridad")

    return {"ui_is_admin": is_admin, "ui_role_name": role_name}
