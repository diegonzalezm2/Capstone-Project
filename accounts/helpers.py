from django.apps import apps

def get_usuario_model():
    for cand in (("personas", "Usuario"), ("accounts", "Usuario")):
        try:
            M = apps.get_model(*cand)
            if M:
                return M
        except Exception:
            pass
    return None

def get_usuario_for(user):
    """
    Devuelve el registro espejo asociado al auth.User (por FK o id).
    """
    Usuario = get_usuario_model()
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

# ---------- utilidades de rol ----------

def _first_attr(obj, names):
    for n in names:
        if hasattr(obj, n):
            return n, getattr(obj, n)
    return None, None

def _find_role_model_candidates():
    cands = []
    for M in apps.get_models():
        name = M.__name__.lower()
        if name in ("rol", "role", "roles"):
            cands.append(M)
    for app_label, model_name in [("rol", "Rol"), ("roles", "Rol"), ("personas", "Rol"), ("accounts", "Rol")]:
        try:
            M = apps.get_model(app_label, model_name)
            if M and M not in cands:
                cands.append(M)
        except Exception:
            pass
    return cands

def _role_obj_from_id(role_id):
    if role_id is None:
        return None
    for M in _find_role_model_candidates():
        try:
            obj = M.objects.filter(pk=role_id).first()
            if obj:
                return obj
        except Exception:
            continue
    return None

def _role_display_name(role_obj):
    if not role_obj:
        return ""
    for field in ("nombre_rol", "nombre", "name", "titulo", "descripcion"):
        if hasattr(role_obj, field):
            val = getattr(role_obj, field)
            if val:
                return str(val)
    return str(role_obj) if role_obj else ""

def resolve_role_name(uapp) -> str:
    if not uapp:
        return ""
    # localizar atributo de rol
    attr, val = _first_attr(uapp, ["rol", "role", "rol_id", "id_rol", "idRol", "id_role"])
    if not attr or val is None:
        return ""
    # si es un objeto (FK)
    if hasattr(val, "_meta"):
        return _role_display_name(val)
    # si es id
    try:
        role_id = int(val)
    except Exception:
        role_id = None
    return _role_display_name(_role_obj_from_id(role_id))

def set_role(uapp, rol_obj):
    """
    Asigna el rol al espejo sin importar si el campo es FK ('rol' / 'role')
    o numérico ('rol_id', 'id_rol', 'idRol', 'id_role').
    """
    if not uapp or not rol_obj:
        return
    field_names = {f.name for f in uapp._meta.get_fields()}

    # Preferir FK si existe
    for name in ("rol", "role"):
        if name in field_names:
            f = uapp._meta.get_field(name)
            is_fk = getattr(getattr(f, "remote_field", None), "model", None) is not None
            if is_fk:
                setattr(uapp, name, rol_obj)
                return

    # Si no hay FK, usar columna numérica
    role_pk = getattr(rol_obj, "pk", None) or getattr(rol_obj, "id", None)
    for name in ("rol_id", "id_rol", "idRol", "id_role"):
        if name in field_names and role_pk is not None:
            setattr(uapp, name, int(role_pk))
            return
