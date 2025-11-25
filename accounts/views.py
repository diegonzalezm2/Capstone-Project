# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponseForbidden

from .utils import db_role_required
from .forms import UserCreateForm, UserEditForm, LoginEmailOrUsernameForm
from .helpers import (
    get_usuario_for,
    get_usuario_model,
    resolve_role_name,
    set_role,
)

Usuario = get_usuario_model()


# ---------- Utilidad: enlazar el espejo Usuario con el User de Django ----------
def _bind_user_relation(uapp, user):
    field_names = {f.name for f in Usuario._meta.get_fields()}

    if "user" in field_names:
        setattr(uapp, "user", user)
        return
    if "auth_user" in field_names:
        setattr(uapp, "auth_user", user)
        return
    if "id_usuario" in field_names:
        f = Usuario._meta.get_field("id_usuario")
        is_fk = getattr(getattr(f, "remote_field", None), "model", None) is not None
        setattr(uapp, "id_usuario", user if is_fk else user.id)
        return


# -------------------- LOGIN / LOGOUT --------------------
def login_view(request):
    if request.method == "POST":
        form = LoginEmailOrUsernameForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Saltar autorización para staff/superuser
            if user.is_staff or user.is_superuser:
                auth_login(request, user)
                messages.success(request, "¡Bienvenido!")
                return redirect("Principal")

            uapp = get_usuario_for(user)
            autorizado = False
            if uapp is not None:
                if hasattr(uapp, "autorizado"):
                    autorizado = bool(uapp.autorizado)
                elif hasattr(uapp, "activo"):
                    autorizado = bool(uapp.activo)

            if not autorizado:
                messages.error(
                    request,
                    "Tu cuenta no está autorizada para iniciar sesión.",
                )
                return render(request, "accounts/login.html", {"form": form})

            auth_login(request, user)
            messages.success(request, "¡Bienvenido!")
            return redirect("Principal")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = LoginEmailOrUsernameForm(request=request)

    return render(request, "accounts/login.html", {"form": form})


@login_required
def logout_confirm(request):
    return render(request, "accounts/logout_confirm.html")


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect("Principal")


# -------------- ADMIN USUARIOS --------------
@login_required
@db_role_required("Administrador", "Jefe de seguridad")
def users_list(request):
    q = request.GET.get("q", "").strip()
    users = User.objects.all().order_by("email")
    if q:
        users = users.filter(email__icontains=q)

    uapp_by_uid = {u.id: get_usuario_for(u) for u in users}

    rows = []
    for u in users:
        uapp = uapp_by_uid.get(u.id)
        rol_name = resolve_role_name(uapp)
        autorizado = False
        if uapp is not None:
            if hasattr(uapp, "autorizado"):
                autorizado = bool(uapp.autorizado)
            elif hasattr(uapp, "activo"):
                autorizado = bool(uapp.activo)

        rows.append(
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "rol": rol_name or "—",
                "autorizado": autorizado,
            }
        )

    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/users_list.html",
        {"page_obj": page_obj, "q": q},
    )


@login_required
@db_role_required("Administrador", "Jefe de seguridad")
@transaction.atomic
def users_create(request):
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            rol = form.cleaned_data["rol"]
            autorizado = form.cleaned_data["autorizado"]
            password = form.cleaned_data["password"]

            if User.objects.filter(email=email).exists():
                messages.error(
                    request,
                    "Ya existe un usuario (Django) con ese correo.",
                )
                return render(
                    request,
                    "accounts/user_form.html",
                    {"form": form, "is_create": True},
                )

            # 1) Crear usuario Django
            u = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            # 2) Crear/actualizar espejo por email si existe (evitar IntegrityError)
            UsuarioModel = get_usuario_model()
            uapp = get_usuario_for(u)
            if not uapp and hasattr(UsuarioModel, "email"):
                uapp = UsuarioModel.objects.filter(email=email).first()
            if not uapp:
                uapp = UsuarioModel()

            # set email si el modelo lo tiene
            if hasattr(uapp, "email"):
                uapp.email = email
            # set nombre si existe
            for name_field in ("nombre", "nombres", "name", "full_name"):
                if hasattr(uapp, name_field) and (first_name or last_name):
                    setattr(
                        uapp,
                        name_field,
                        f"{first_name} {last_name}".strip(),
                    )

            _bind_user_relation(uapp, u)
            set_role(uapp, rol)

            if hasattr(uapp, "autorizado"):
                uapp.autorizado = autorizado
            elif hasattr(uapp, "activo"):
                uapp.activo = autorizado

            try:
                uapp.save()
            except IntegrityError:
                # Si chocó por email único en espejo, cancelar también Django User recién creado
                u.delete()
                messages.error(
                    request,
                    "Ese correo ya existe en la tabla de usuarios de la aplicación.",
                )
                return render(
                    request,
                    "accounts/user_form.html",
                    {"form": form, "is_create": True},
                )

            messages.success(request, "Usuario creado correctamente.")
            return redirect("accounts_users_list")
    else:
        form = UserCreateForm()

    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "is_create": True},
    )


@login_required
@db_role_required("Administrador", "Jefe de seguridad")
@transaction.atomic
def users_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    uapp = get_usuario_for(user) or Usuario()

    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "rol": getattr(uapp, "rol", None),  # si es FK, Django pinta el select
        "autorizado": (
            bool(getattr(uapp, "autorizado"))
            if hasattr(uapp, "autorizado")
            else bool(getattr(uapp, "activo"))
            if hasattr(uapp, "activo")
            else False
        ),
    }

    if request.method == "POST":
        form = UserEditForm(request.POST)
        if form.is_valid():
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.save(update_fields=["first_name", "last_name"])

            _bind_user_relation(uapp, user)
            set_role(uapp, form.cleaned_data["rol"])

            autorizado_flag = form.cleaned_data["autorizado"]
            if hasattr(uapp, "autorizado"):
                uapp.autorizado = autorizado_flag
            elif hasattr(uapp, "activo"):
                uapp.activo = autorizado_flag

            uapp.save()

            messages.success(request, "Usuario actualizado correctamente.")
            return redirect("accounts_users_list")
    else:
        form = UserEditForm(initial=initial)

    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "is_create": False, "user_obj": user},
    )


@login_required
@db_role_required("Administrador", "Jefe de seguridad")
@transaction.atomic
def users_toggle_authorized(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    uapp = get_usuario_for(user) or Usuario()

    flag_actual = (
        bool(getattr(uapp, "autorizado"))
        if hasattr(uapp, "autorizado")
        else bool(getattr(uapp, "activo"))
        if hasattr(uapp, "activo")
        else False
    )
    nuevo = not flag_actual

    if hasattr(uapp, "autorizado"):
        uapp.autorizado = nuevo
    elif hasattr(uapp, "activo"):
        uapp.activo = nuevo

    _bind_user_relation(uapp, user)
    uapp.save()

    messages.success(
        request,
        f"Autorización cambiada a: {'Sí' if nuevo else 'No'}",
    )
    return redirect("accounts_users_list")


@login_required
@db_role_required("Administrador", "Jefe de seguridad")
@transaction.atomic
def users_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if request.user.id == user.id:
        messages.error(
            request,
            "No puedes eliminar tu propio usuario.",
        )
        return redirect("accounts_users_list")
    if user.is_superuser:
        messages.error(
            request,
            "No puedes eliminar un superusuario.",
        )
        return redirect("accounts_users_list")

    if request.method == "POST":
        uapp = get_usuario_for(user)
        if uapp:
            uapp.delete()
        user.delete()
        messages.success(request, "Usuario eliminado correctamente.")
        return redirect("accounts_users_list")

    return render(
        request,
        "accounts/user_confirm_delete.html",
        {"user_obj": user},
    )


# --------- Endpoint de emergencia: reautorizar por email (solo staff) ----------
@login_required
def reautorizar_por_email(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Solo staff.")

    email = request.GET.get("email")
    if not email:
        return JsonResponse({"ok": False, "msg": "Falta ?email="}, status=400)

    try:
        u = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "msg": "No existe ese email"}, status=404)

    UsuarioModel = get_usuario_model()
    if not UsuarioModel:
        return JsonResponse(
            {"ok": False, "msg": "Modelo espejo no encontrado"},
            status=500,
        )

    field_names = {f.name for f in UsuarioModel._meta.get_fields()}
    uapp = None
    for fk in ("user", "auth_user", "id_usuario"):
        if fk in field_names:
            try:
                uapp = UsuarioModel.objects.get(**{fk: u})
                break
            except Exception:
                try:
                    uapp = UsuarioModel.objects.get(**{fk: u.id})
                    break
                except Exception:
                    pass
    if uapp is None:
        uapp = UsuarioModel()
        if "user" in field_names:
            setattr(uapp, "user", u)
        elif "auth_user" in field_names:
            setattr(uapp, "auth_user", u)
        elif "id_usuario" in field_names:
            try:
                setattr(uapp, "id_usuario", u)
            except Exception:
                setattr(uapp, "id_usuario", u.id)

    if "autorizado" in field_names:
        setattr(uapp, "autorizado", True)
    elif "activo" in field_names:
        setattr(uapp, "activo", True)

    uapp.save()
    return JsonResponse({"ok": True, "msg": f"{email} autorizado"})
