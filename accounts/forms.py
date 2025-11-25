# accounts/forms.py
from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError

UserModel = get_user_model()


def get_Usuario_model():
    for candidate in (("personas", "Usuario"), ("accounts", "Usuario")):
        try:
            M = apps.get_model(*candidate)
            if M:
                return M
        except Exception:
            pass
    raise LookupError("No se encontró el modelo 'Usuario'.")


def get_Rol_model():
    for candidate in (("personas", "Rol"), ("accounts", "Rol")):
        try:
            M = apps.get_model(*candidate)
            if M:
                return M
        except Exception:
            pass
    raise LookupError("No se encontró el modelo 'Rol'.")


Usuario = get_Usuario_model()
Rol = get_Rol_model()


class UserCreateForm(forms.Form):
    email = forms.EmailField(
        label="Correo",
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "placeholder": "correo@dominio.cl"}
        ),
    )
    first_name = forms.CharField(
        label="Nombres",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre(s)"}
        ),
    )
    last_name = forms.CharField(
        label="Apellidos",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Apellido(s)"}
        ),
    )
    rol = forms.ModelChoiceField(
        label="Rol",
        queryset=Rol.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    autorizado = forms.BooleanField(
        label="Autorizado para iniciar sesión",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    password = forms.CharField(
        label="Contraseña temporal",
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "********"}
        ),
    )


class UserEditForm(forms.Form):
    first_name = forms.CharField(
        label="Nombres",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre(s)"}
        ),
    )
    last_name = forms.CharField(
        label="Apellidos",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Apellido(s)"}
        ),
    )
    rol = forms.ModelChoiceField(
        label="Rol",
        queryset=Rol.objects.all(),
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    autorizado = forms.BooleanField(
        label="Autorizado para iniciar sesión",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


# ---------------------------------------------------------------------
# Formulario de login que acepta usuario O correo electrónico
# ---------------------------------------------------------------------
class LoginEmailOrUsernameForm(forms.Form):
    username = forms.CharField(
        label="Usuario o correo",
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "usuario o correo@dominio.cl",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        required=True,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "********"}
        ),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username_or_email = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if not username_or_email or not password:
            raise ValidationError("Usuario o contraseña incorrectos.")

        user = None

        # 1) Primero intentamos autenticar como si fuera username normal
        user = authenticate(
            self.request, username=username_or_email, password=password
        )

        # 2) Si no funcionó, probamos tratarlo como email.
        if not user:
            # Pueden existir varios usuarios con el mismo email -> NUNCA usamos get()
            candidatos = UserModel.objects.filter(email__iexact=username_or_email)
            for cand in candidatos:
                user = authenticate(
                    self.request, username=cand.username, password=password
                )
                if user:
                    break

        if not user:
            raise ValidationError("Usuario o contraseña incorrectos.")

        self.user_cache = user
        return cleaned_data

    def get_user(self):
        return self.user_cache
