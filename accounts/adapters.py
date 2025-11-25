# accounts/adapters.py
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.apps import apps

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse


def _get_usuario_for(user):
    """
    Devuelve el registro espejo de tu modelo Usuario (personas.Usuario o
    accounts.Usuario) enlazado a auth.User, tolerando FK o entero.
    """
    Usuario = None
    for cand in (("personas", "Usuario"), ("accounts", "Usuario")):
        try:
            M = apps.get_model(*cand)
            if M:
                Usuario = M
                break
        except Exception:
            pass
    if not Usuario:
        return None

    field_names = {f.name for f in Usuario._meta.get_fields()}
    for fk_name in ("user", "auth_user", "id_usuario", "user_id"):
        if fk_name not in field_names:
            continue
        for candidate in (user, getattr(user, "id", None)):
            if candidate is None:
                continue
            try:
                return Usuario.objects.get(**{fk_name: candidate})
            except Exception:
                pass
    return None


def _is_authorized(user) -> bool:
    """
    True si el espejo de Usuario indica autorizado/activo.
    """
    uapp = _get_usuario_for(user)
    if not uapp:
        return False
    if hasattr(uapp, "autorizado"):
        return bool(getattr(uapp, "autorizado"))
    if hasattr(uapp, "activo"):
        return bool(getattr(uapp, "activo"))
    return False


class AccountAdapter(DefaultAccountAdapter):
    """
    Desactiva el registro por formulario clásico de allauth.
    """
    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Valida SIEMPRE la autorización, tanto para cuentas nuevas como existentes.
    Además, muestra mensajes claros y corta el flujo cuando corresponde.
    """
    def pre_social_login(self, request, sociallogin):
        # 1) Si la socialaccount ya existe, validar autorización del usuario dueño
        if sociallogin.is_existing:
            user = sociallogin.user or getattr(sociallogin.account, "user", None)
            if user and not _is_authorized(user):
                messages.error(
                    request,
                    "Tu cuenta fue desautorizada. Contacta al Jefe de Seguridad."
                )
                raise ImmediateHttpResponse(redirect("login"))
            return  # autorizado: continuar login normal

        # 2) Si NO existe la socialaccount: resolver por email
        email = (sociallogin.account.extra_data or {}).get("email")
        if not email:
            messages.error(request, "No pudimos obtener tu correo de Google.")
            raise ImmediateHttpResponse(redirect("login"))

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(
                request,
                "Tu cuenta no está registrada ni autorizada. "
                "Habla con el Jefe de Seguridad para que te habiliten."
            )
            raise ImmediateHttpResponse(redirect("login"))

        # 3) Existe en Django: validar autorización antes de conectar
        if not _is_authorized(user):
            messages.error(
                request,
                "Tu cuenta existe, pero NO está autorizada para iniciar sesión. "
                "Contacta al Jefe de Seguridad."
            )
            raise ImmediateHttpResponse(redirect("login"))

        # 4) OK: conectar la socialaccount con el usuario encontrado
        sociallogin.connect(request, user)
