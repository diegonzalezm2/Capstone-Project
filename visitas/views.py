# visitas/views.py
import json
import re
from urllib.parse import urlparse, parse_qs, unquote_plus

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

# IMPORTA TUS MODELOS (ajusta rutas de apps si difieren)
from personas.models import Persona
from lugares.models import Lugar
from visitas.models import Visita


# =========================
# Utilidades: RUT en Chile
# =========================
def _rut_dv(number: int) -> str:
    """Calcula dígito verificador chileno."""
    s = 1
    m = 0
    while number:
        s = (s + number % 10 * (9 - m % 6)) % 11
        number //= 10
        m += 1
    return "K" if s == 0 else str(s - 1).upper()


def _clean_rut(rut_str: str) -> str:
    return re.sub(r"[^0-9kK-]", "", rut_str or "").upper()


def _parse_rut(text: str):
    """
    Busca un RUT válido dentro del texto.
    Retorna ('12.345.678-9', '12345678', '9') o None.
    """
    text = text or ""
    patt = re.compile(r"(\d{1,2}\.?\d{3}\.?\d{3})[ -]?-?([0-9Kk])")
    m = patt.search(text.replace(" ", ""))
    if not m:
        return None

    body = re.sub(r"\D", "", m.group(1))
    dv = m.group(2).upper()
    if not body:
        return None

    try:
        if _rut_dv(int(body)) != dv:
            return None
    except ValueError:
        return None

    # RUT formateado con puntos
    body_int = int(body)
    rut_fmt = f"{body_int:,}".replace(",", ".") + "-" + dv
    return rut_fmt, body, dv


# =========================
# Utilidades: Nombre
# =========================
def _best_name_guess(raw: str) -> str:
    """
    Heurística simple para obtener un nombre decente desde el texto del QR.
    Primero busca en querystring (NOMBRES/APELLIDOS), luego por líneas “tipo nombre”.
    """
    raw = raw or ""

    # 1) Intento por query-string
    try:
        q = parse_qs(urlparse(raw).query)
        # NOMBRES + APELLIDOS
        if "NOMBRES" in q and "APELLIDOS" in q:
            nom = unquote_plus(q["NOMBRES"][0]).strip()
            ape = unquote_plus(q["APELLIDOS"][0]).strip()
            return (nom + " " + ape).title()

        # NOMBRE / NAME / FULLNAME
        for key in ("NOMBRE", "NAME", "FULLNAME"):
            if key in q:
                return unquote_plus(q[key][0]).strip().title()
    except Exception:
        pass

    # 2) Heurística por líneas “con pinta de nombre”
    lines = [l.strip() for l in re.split(r"[\r\n|]+", raw) if l.strip()]
    cands = []
    for ln in lines:
        ln2 = re.sub(r"[^A-Za-zÁÉÍÓÚÑÜáéíóúñü\s]", " ", ln).strip()
        if len(ln2) >= 4 and len(ln2.split()) >= 2 and len(re.findall(r"\d", ln)) <= 2:
            cands.append(ln2)
    return (max(cands, key=len) if cands else "").title()


# =========================
# Parser principal
# =========================
def parse_id_payload(raw: str):
    """
    Extrae RUT (válido) y Nombre desde el raw del QR/PDF417.
    Retorna dict: {'rut_fmt','rut','dv','nombre'} o None.
    """
    if not raw:
        return None

    # 1) RUN/RUT en querystring
    try:
        q = parse_qs(urlparse(raw).query)
        for k in ("RUN", "RUT"):
            if k in q:
                candidate = _clean_rut(q[k][0])
                fmt = _parse_rut(candidate)
                if fmt:
                    rut_fmt, body, dv = fmt
                    nombre = _best_name_guess(raw)
                    return {"rut_fmt": rut_fmt, "rut": body, "dv": dv, "nombre": nombre}
    except Exception:
        pass

    # 2) RUT en el texto
    fmt = _parse_rut(raw)
    if fmt:
        rut_fmt, body, dv = fmt
        nombre = _best_name_guess(raw)
        return {"rut_fmt": rut_fmt, "rut": body, "dv": dv, "nombre": nombre}

    return None


# =========================
# Persistencia
# =========================
def _split_nombre(nombre: str):
    """Divide nombre completo en (nombres, apellidos) de forma muy básica."""
    nombre = (nombre or "").strip()
    if not nombre:
        return "", ""
    parts = nombre.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _ensure_persona(rut_body: str, nombre: str):
    """
    Crea/actualiza Persona por RUT.
    Se asume modelo con campos:
      - run (char único)
      - nombres (char)
      - apellidos (char)
    AJUSTA si tus campos son distintos.
    """
    nombres, apellidos = _split_nombre(nombre)

    p, created = Persona.objects.get_or_create(
        run=rut_body,                     # <-- AJUSTA si tu campo no es 'run'
        defaults={"nombres": nombres, "apellidos": apellidos}
    )

    # Si luego obtenemos un nombre “mejor”, lo actualizamos.
    changed = False
    if nombres and (created or not getattr(p, "nombres", "")):
        p.nombres = nombres
        changed = True
    if apellidos and (created or not getattr(p, "apellidos", "")):
        p.apellidos = apellidos
        changed = True
    if changed:
        p.save(update_fields=["nombres", "apellidos"])

    return p


def _visita_abierta(persona):
    """
    Devuelve la última visita abierta (salida_at is NULL), si existe.
    Asume modelo Visita con:
      - persona (FK)
      - entrada_at (datetime)
      - salida_at (datetime, null=True)
    """
    return (
        Visita.objects
        .filter(persona=persona, salida_at__isnull=True)
        .order_by("-id")
        .first()
    )


def _registrar_ingreso(persona, lugar, user):
    """
    Crea una nueva visita con entrada_at=ahora.
    Intenta rellenar operador_entrada_id o email si existen esos campos.
    """
    v = Visita(persona=persona, lugar=lugar)  # <-- AJUSTA si tu FK se llama distinto
    now = timezone.now()

    # Campos típicos
    if hasattr(v, "entrada_at"):
        v.entrada_at = now
    if hasattr(v, "operador_entrada_id") and user and hasattr(user, "id"):
        setattr(v, "operador_entrada_id", getattr(user, "id"))
    if hasattr(v, "email") and user and getattr(user, "email", None):
        v.email = user.email

    v.save()
    return v


def _registrar_egreso(visita_abierta, user):
    """
    Marca salida_at=ahora en la visita abierta.
    Intenta rellenar operador_salida_id si existe.
    """
    now = timezone.now()
    if hasattr(visita_abierta, "salida_at"):
        visita_abierta.salida_at = now
    if hasattr(visita_abierta, "operador_salida_id") and user and hasattr(user, "id"):
        setattr(visita_abierta, "operador_salida_id", getattr(user, "id"))
    visita_abierta.save(update_fields=["salida_at"] + (
        ["operador_salida_id"] if hasattr(visita_abierta, "operador_salida_id") else []
    ))
    return visita_abierta


# =========================
# Vistas
# =========================
@login_required
def scan_view(request):
    """
    Página del escáner. Renderiza 'visitas/scan.html'
    y envía opcionalmente los lugares para un selector (si lo usas en la UI).
    """
    destinos = Lugar.objects.all().only("id", "nombre_lugar")  # <-- AJUSTA nombre del campo si difiere
    return render(request, "visitas/scan.html", {"destinos": destinos})


@login_required
@require_POST
@transaction.atomic
def scan_api(request):
    """
    API POST JSON:
      { "raw": "<texto del QR/PDF417>", "destino_id": <opcional> }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    raw = (payload.get("raw") or "").strip()
    if not raw:
        return JsonResponse({"ok": False, "msg": "Payload vacío."})

    data = parse_id_payload(raw)
    if not data:
        return JsonResponse({"ok": False, "msg": "No se pudo leer un RUT válido."})

    # Persona por RUN
    persona = _ensure_persona(data["rut"], data.get("nombre"))

    # Lugar destino
    destino = None
    destino_id = payload.get("destino_id")
    if destino_id:
        try:
            destino = Lugar.objects.get(pk=destino_id)
        except Lugar.DoesNotExist:
            destino = None
    if not destino:
        destino = Lugar.objects.order_by("id").first()  # <-- AJUSTA lógica por defecto

    # ¿Tiene visita abierta?
    abierta = _visita_abierta(persona)
    if abierta:
        _registrar_egreso(abierta, request.user)
        accion = "Egreso"
        visita_id = abierta.id
    else:
        v = _registrar_ingreso(persona, destino, request.user)
        accion = "Ingreso"
        visita_id = v.id

    nombre_mostrar = (
        (getattr(persona, "nombres", "") + " " + getattr(persona, "apellidos", "")).strip()
        or getattr(persona, "nombre", "")  # por si tu modelo usa 'nombre'
        or "(sin nombre)"
    )

    return JsonResponse({
        "ok": True,
        "msg": f"{accion} registrado: {nombre_mostrar} ({data['rut_fmt']}).",
        "rut": data["rut_fmt"],
        "nombre": nombre_mostrar,
        "accion": accion,
        "destino": getattr(destino, "nombre_lugar", None) or getattr(destino, "nombre", None),
        "visita_id": visita_id,
    })
