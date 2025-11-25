from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from datetime import datetime, time as dtime
import json
import re
from urllib.parse import urlparse, parse_qs

from personas.models import Persona
from lugares.models import Lugar
from accounts.models import Usuario
from accounts.utils import db_role_required
from .models import Visita

# ---------- Utilidades RUT ----------
RUT_RE = re.compile(r'([0-9]{6,9}-?[0-9kK])')


def normalize_rut(raw: str) -> str:
    if not raw:
        return ""
    only = re.sub(r'[^0-9kK]', '', str(raw)).upper()
    if len(only) < 2:
        return only
    return f"{only[:-1]}-{only[-1]}"


def rut_from_text_or_url(text: str) -> str:
    if not text:
        return ""
    s = str(text).strip()
    # 1) Si viene URL (o string con ?), intenta leer parámetro RUN/run
    try:
        parsed = urlparse(s if s.startswith("http") else "http://dummy" + s)
        qs = parse_qs(parsed.query)
        for key in ("RUN", "run", "Rut", "rut"):
            if key in qs and qs[key]:
                return normalize_rut(qs[key][0])
    except Exception:
        pass
    # 2) Si viene “texto común”, extrae por regex
    m = RUT_RE.search(s)
    if m:
        return normalize_rut(m.group(1))
    # 3) Último intento: normalizar el string completo
    return normalize_rut(s)


# ---------- Operador (autoprovisión si no existe) ----------
def _get_or_create_operador_from_django_user(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None

    email = (getattr(request.user, "email", "") or "").strip()
    username = (getattr(request.user, "username", "") or "").strip() or email

    # Buscar por email
    if email:
        try:
            return Usuario.objects.get(email=email, activo=True)
        except Usuario.DoesNotExist:
            pass

    # Buscar por nombre de usuario
    if username:
        try:
            return Usuario.objects.get(nombre=username, activo=True)
        except Usuario.DoesNotExist:
            pass

    # ¿Se permite autoprovisión?
    if not getattr(settings, "AUTO_PROVISION_OPERADOR", True):
        return None

    rol_id = getattr(settings, "OPERADOR_DEFAULT_ROL_ID", 1)
    try:
        op = Usuario.objects.create(
            nombre=username or (email.split("@")[0] if email else "operador"),
            email=email or None,
            hash_password="",
            rol_id=rol_id,
            activo=True,
        )
        return op
    except Exception:
        try:
            return (
                Usuario.objects.filter(activo=True)
                .order_by("id_usuario")
                .first()
            )
        except Exception:
            return None


# ---------- Escáner ----------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
def scan_view(request):
    destinos = list(Lugar.objects.all().order_by("nombre_lugar"))
    return render(request, "visitas/scan.html", {"destinos": destinos})


@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["POST"])
def scan_api(request):
    """
    JSON: { rut, nombre?, fecha_hora?, destino_id?, dry_run? }
    - dry_run=True: no exige destino_id; devuelve inside True/False y no guarda.
    - dry_run=False: valida destino_id, crea visita si no hay abierta.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "message": "JSON inválido."}, status=400
        )

    rut_raw = payload.get("rut") or ""
    destino_id = payload.get("destino_id")
    dry_run = bool(payload.get("dry_run", False))

    rut = rut_from_text_or_url(rut_raw)
    if not rut:
        return JsonResponse(
            {"ok": False, "message": "RUT no válido."}, status=400
        )

    persona = Persona.objects.filter(run=rut).first()

    # Dry run: solo consulta si está adentro
    if dry_run:
        inside = False
        if persona:
            inside = Visita.objects.filter(
                persona=persona, salida_at__isnull=True
            ).exists()
        return JsonResponse({"ok": True, "inside": inside}, status=200)

    # Flujo normal (registrar ingreso)
    if not destino_id:
        return JsonResponse(
            {
                "ok": False,
                "message": "Debe seleccionar el lugar de destino.",
            },
            status=400,
        )

    try:
        lugar = Lugar.objects.get(pk=int(destino_id))
    except (Lugar.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {"ok": False, "message": "Destino no encontrado."}, status=404
        )

    if not persona:
        persona = Persona.objects.create(
            run=rut,
            nombres=(payload.get("nombre") or "").strip()[:100],
            apellidos="",
            is_inside=False,
        )

    if Visita.objects.filter(
        persona=persona, salida_at__isnull=True
    ).exists():
        return JsonResponse(
            {
                "ok": False,
                "message": "La persona ya se encuentra dentro (visita abierta).",
            },
            status=200,
        )

    operador = _get_or_create_operador_from_django_user(request)
    if operador is None:
        return JsonResponse(
            {
                "ok": False,
                "message": "No se pudo determinar/crear el operador.",
            },
            status=403,
        )

    with transaction.atomic():
        now = timezone.now()
        v = Visita.objects.create(
            persona=persona,
            entrada_at=now,
            operador_entrada=operador,
            lugar=lugar,
        )
        Persona.objects.filter(pk=persona.id_persona).update(is_inside=True)

    return JsonResponse(
        {
            "ok": True,
            "message": f"Ingreso registrado (Visita #{v.id_visita}).",
        },
        status=201,
    )


# ---------- Listado ----------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
def visitas_list_view(request):
    """Página del listado; la data se carga por JS."""
    return render(request, "visitas/listado.html")


@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def visitas_list_api(request):
    """Devuelve JSON de visitas. Admite ?q=<texto> para búsqueda simple."""
    q = (request.GET.get("q") or "").strip().lower()

    visitas = (
        Visita.objects.select_related("persona", "lugar")
        .order_by("-entrada_at")
    )

    rows = []
    for v in visitas:
        nombre = f"{v.persona.nombres or ''} {v.persona.apellidos or ''}".strip()
        rut = v.persona.run
        lugar = v.lugar.nombre_lugar if v.lugar_id else ""
        estado = "Dentro" if v.salida_at is None else "Fuera"

        texto = f"{nombre} {rut} {lugar} {estado}".lower()
        if q and q not in texto:
            continue

        rows.append(
            {
                "id": v.id_visita,
                "nombre": nombre,
                "rut": rut,
                "lugar": lugar,
                "entrada_at": (
                    v.entrada_at.strftime("%Y-%m-%d %H:%M:%S")
                    if v.entrada_at
                    else ""
                ),
                "salida_at": (
                    v.salida_at.strftime("%Y-%m-%d %H:%M:%S")
                    if v.salida_at
                    else ""
                ),
                "estado": estado,
                "abierta": v.salida_at is None,  # para separar en 2 columnas
            }
        )

    return JsonResponse({"ok": True, "rows": rows}, status=200)


# ---------- Cerrar visita ----------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["POST"])
def visita_close_api(request):
    """
    Cierra una visita (marca salida).
    Body JSON: { "visita_id": <int> }
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        visita_id = int(payload.get("visita_id"))
    except Exception:
        return JsonResponse(
            {"ok": False, "message": "Payload inválido."}, status=400
        )

    v = (
        Visita.objects.filter(pk=visita_id)
        .select_related("persona")
        .first()
    )
    if not v:
        return JsonResponse(
            {"ok": False, "message": "Visita no encontrada."}, status=404
        )

    if v.salida_at:
        return JsonResponse(
            {"ok": True, "message": "La visita ya estaba cerrada."}, status=200
        )

    with transaction.atomic():
        v.salida_at = timezone.now()
        v.save(update_fields=["salida_at"])
        # Si llevas flag en Persona, lo actualizamos:
        if v.persona_id:
            Persona.objects.filter(pk=v.persona.id_persona).update(
                is_inside=False
            )

    return JsonResponse(
        {"ok": True, "message": "Salida registrada correctamente."}, status=200
    )


# ---------- Ingreso Manual ----------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
def manual_view(request):
    """Página para el formulario de ingreso manual."""
    destinos = list(Lugar.objects.all().order_by("nombre_lugar"))
    return render(request, "visitas/manual.html", {"destinos": destinos})


@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["POST"])
def manual_api(request):
    """
    JSON: { nombre, rut, destino_id, hora }
    - hora opcional (HH:MM). Si no viene, usa ahora.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "message": "JSON inválido."}, status=400
        )

    nombre = (payload.get("nombre") or "").strip()
    rut = rut_from_text_or_url(payload.get("rut") or "")
    destino_id = payload.get("destino_id")
    hora_str = (payload.get("hora") or "").strip()

    if not rut:
        return JsonResponse(
            {"ok": False, "message": "RUT no válido."}, status=400
        )
    if not destino_id:
        return JsonResponse(
            {"ok": False, "message": "Debe seleccionar la ubicación."},
            status=400,
        )

    try:
        lugar = Lugar.objects.get(pk=int(destino_id))
    except (Lugar.DoesNotExist, ValueError, TypeError):
        return JsonResponse(
            {"ok": False, "message": "Ubicación no encontrada."}, status=404
        )

    persona = Persona.objects.filter(run=rut).first()
    if not persona:
        persona = Persona.objects.create(
            run=rut,
            nombres=nombre[:100] if nombre else "",
            apellidos="",
            is_inside=False,
        )

    if Visita.objects.filter(
        persona=persona, salida_at__isnull=True
    ).exists():
        return JsonResponse(
            {
                "ok": False,
                "message": "Esta persona ya tiene una visita abierta.",
            },
            status=200,
        )

    # Construir datetime de entrada
    now = timezone.localtime()
    if hora_str:
        try:
            hh, mm = [int(x) for x in hora_str.split(":", 1)]
            custom_time = dtime(hour=hh, minute=mm)
            entrada_at = timezone.make_aware(
                datetime.combine(now.date(), custom_time), now.tzinfo
            )
        except Exception:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "Hora inválida. Use formato HH:MM.",
                },
                status=400,
            )
    else:
        entrada_at = now

    operador = _get_or_create_operador_from_django_user(request)
    if operador is None:
        return JsonResponse(
            {
                "ok": False,
                "message": "No se pudo determinar/crear el operador.",
            },
            status=403,
        )

    with transaction.atomic():
        v = Visita.objects.create(
            persona=persona,
            entrada_at=entrada_at,
            operador_entrada=operador,
            lugar=lugar,
        )
        Persona.objects.filter(pk=persona.id_persona).update(is_inside=True)

    return JsonResponse(
        {
            "ok": True,
            "message": f"Ingreso manual registrado (Visita #{v.id_visita}).",
        },
        status=201,
    )
