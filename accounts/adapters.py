# accounts/adapters.py
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount.helpers import complete_social_login  # 👈 importante

User = get_user_model()

class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False

class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        """
        Permitir login sólo si el email ya existe como usuario local.
        Si existe, completamos el login social para ese usuario.
        Si NO existe, cancelamos y regresamos al login con un mensaje.
        """
        email = sociallogin.account.extra_data.get("email")
        if not email:
            messages.error(request, "No pudimos obtener tu email de Google.")
            raise ImmediateHttpResponse(redirect("login"))

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            messages.error(
                request,
                "Tu cuenta no está autorizada. Pide al Jefe de Seguridad que te registre."
            )
            raise ImmediateHttpResponse(redirect("login"))

        # Si la cuenta social ya está vinculada, allauth seguirá el flujo normal
        if sociallogin.is_existing:
            return

        # 👉 Decirle a allauth que finalice el login como ese usuario existente
        sociallogin.user = user
        response = complete_social_login(request, sociallogin)
        # complete_social_login devuelve una HttpResponse: detenemos el pipeline aquí
        raise ImmediateHttpResponse(response)
