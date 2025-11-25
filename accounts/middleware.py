# accounts/middleware.py
from django.shortcuts import redirect
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages

from .helpers import get_usuario_for

SAFE_PREFIXES = (
    "/admin/",                 # no bloquear admin
    "/accounts/_reauth/",      # reautorizar por email
    "/accounts/logout",        # logout
    "/accounts/google",        # prefijo del flujo social (ajústalo si cambia)
    "/auth/",                  # allauth social callbacks
    "/static/", "/media/",     # estáticos / media
)

SAFE_URLNAMES = {
    "login", "logout", "reauth_temp",           # tus nombres de url
    "account_login", "account_logout",          # allauth
    "socialaccount_login", "socialaccount_connections",
}

class RequireAuthorizedMiddleware(MiddlewareMixin):
    """
    Bloquea el acceso de usuarios desautorizados, excepto:
      - superusuarios o staff (admin)
      - rutas seguras (admin, login/logout, static, callbacks, reauth)
    Lee 'autorizado' o 'activo' desde el espejo Usuario.
    """

    def process_request(self, request):
        # Si no está autenticado, nada que hacer
        if not request.user.is_authenticated:
            return None

        # Bypass: admin/superuser no requieren autorización
        if request.user.is_superuser or request.user.is_staff:
            return None

        # Bypass por path
        path = request.path or ""
        if path.startswith(SAFE_PREFIXES):
            return None

        # Bypass por nombre de URL conocido
        try:
            match = resolve(path)
            if match.url_name in SAFE_URLNAMES:
                return None
        except Exception:
            pass

        # Revisa estado en el espejo
        uapp = get_usuario_for(request.user)
        is_ok = False
        if uapp:
            if hasattr(uapp, "autorizado"):
                is_ok = bool(getattr(uapp, "autorizado"))
            elif hasattr(uapp, "activo"):
                is_ok = bool(getattr(uapp, "activo"))

        if not is_ok:
            messages.error(request, "Tu cuenta fue desautorizada. Contacta al Jefe de Seguridad.")
            return redirect("login")  # nombre de tu vista de login

        return None
