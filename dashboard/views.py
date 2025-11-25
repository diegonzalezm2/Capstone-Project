# dashboard/views.py
from datetime import datetime, timedelta, timezone as dt_tz
from collections import OrderedDict
import csv

from django.http import JsonResponse, HttpResponse
from django.db.models import (
    Count,
    F,
    ExpressionWrapper,
    DateTimeField,
    CharField,
    Value,
)
from django.db.models.functions import TruncHour
from django.db.models.expressions import Func
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from visitas.models import Visita
from lugares.models import Lugar  # <--- IMPORTANTE
from accounts.utils import db_role_required  # <--- ROLES

# Zona horaria local (Chile continental)
CL_TZ = dt_tz(timedelta(hours=-3))


@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
def dashboard_home(request):
    lugares = list(
        Lugar.objects.order_by("nombre_lugar")
        .values_list("nombre_lugar", flat=True)
        .distinct()
    )
    # nombres de guardias que realmente han registrado visitas
    guardias = list(
        Visita.objects.exclude(operador_entrada__isnull=True)
        .values_list("operador_entrada__nombre", flat=True)
        .distinct()
        .order_by("operador_entrada__nombre")
    )
    return render(
        request,
        "dashboard/graficos.html",
        {
            "lugares": lugares,
            "guardias": guardias,
        },
    )


# ---------------- Utilidades de tiempo ----------------
def _today_bounds_local():
    now_local = datetime.now(dt_tz.utc).astimezone(CL_TZ)
    start_local = now_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(dt_tz.utc)
    end_utc = end_local.astimezone(dt_tz.utc)
    return start_local, end_local, start_utc, end_utc


def _day_bounds_local(dt_local):
    start_local = dt_local.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end_local = start_local + timedelta(days=1)
    return (
        start_local,
        end_local,
        start_local.astimezone(dt_tz.utc),
        end_local.astimezone(dt_tz.utc),
    )


# ---------------- API: Resumen general ----------------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def api_summary(request):
    try:
        _, _, today_start_utc, today_end_utc = _today_bounds_local()

        today_count = (
            Visita.objects.filter(
                entrada_at__gte=today_start_utc,
                entrada_at__lt=today_end_utc,
            ).count()
        )
        inside_now = Visita.objects.filter(salida_at__isnull=True).count()

        labels_14d, values_14d = [], []
        for i in range(13, -1, -1):
            loc = datetime.now(CL_TZ) - timedelta(days=i)
            d0_local, _, d0_utc, d1_utc = _day_bounds_local(loc)
            c = Visita.objects.filter(
                entrada_at__gte=d0_utc, entrada_at__lt=d1_utc
            ).count()
            labels_14d.append(d0_local.strftime("%d-%m"))
            values_14d.append(c)

        q_hour = (
            Visita.objects.filter(
                entrada_at__gte=today_start_utc,
                entrada_at__lt=today_end_utc,
            )
            .annotate(h=TruncHour("entrada_at", tzinfo=dt_tz.utc))
            .values("h")
            .annotate(c=Count("h"))
            .order_by("h")
        )
        by_hour_labels = [f"{h:02d}:00" for h in range(24)]
        by_hour_values = [0] * 24
        for row in q_hour:
            h_utc = row["h"]
            h_local = h_utc.astimezone(CL_TZ).hour
            by_hour_values[h_local] += row["c"]

        q_loc = (
            Visita.objects.filter(
                entrada_at__gte=today_start_utc,
                entrada_at__lt=today_end_utc,
            )
            .annotate(loc=F("lugar__nombre_lugar"))
            .values("loc")
            .annotate(c=Count("loc"))
            .order_by("-c")
        )
        by_location_labels = [r["loc"] for r in q_loc]
        by_location_values = [r["c"] for r in q_loc]

        week_start_local = (
            datetime.now(CL_TZ).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            - timedelta(days=6)
        )
        _, _, week_start_utc, _ = _day_bounds_local(week_start_local)
        q_top = (
            Visita.objects.filter(
                entrada_at__gte=week_start_utc,
                entrada_at__lt=today_end_utc,
            )
            .annotate(doc=F("persona__run"))
            .values("doc")
            .annotate(c=Count("doc"))
            .order_by("-c")[:10]
        )
        top_visitors_labels = [r["doc"] for r in q_top]
        top_visitors_values = [r["c"] for r in q_top]

        data = {
            "ok": True,
            "kpis": {"today": today_count, "inside_now": inside_now},
            "series_14d": {
                "labels": labels_14d,
                "values": values_14d,
            },
            "by_hour": {
                "labels": by_hour_labels,
                "values": by_hour_values,
            },
            "by_location_today": {
                "labels": by_location_labels,
                "values": by_location_values,
            },
            "top_visitors_week": {
                "labels": top_visitors_labels,
                "values": top_visitors_values,
            },
        }
        return JsonResponse(data)
    except Exception as e:
        print("[dashboard.api_summary] ERROR:", e)
        return JsonResponse({"ok": False, "message": str(e)}, status=500)


# ---------------- API: Gráfico mensual ----------------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def api_monthly(request):
    try:
        now_local = datetime.now(dt_tz.utc).astimezone(CL_TZ)
        current_month_local = now_local.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        start_local = (current_month_local - timedelta(days=365)).replace(
            day=1
        )

        start_utc = start_local.astimezone(dt_tz.utc)
        end_utc = now_local.astimezone(dt_tz.utc)

        local_dt = ExpressionWrapper(
            F("entrada_at") + timedelta(hours=-3),
            output_field=DateTimeField(),
        )
        month_key = Func(
            local_dt,
            Value("%Y-%m"),
            function="DATE_FORMAT",
            output_field=CharField(),
        )

        qs = (
            Visita.objects.filter(
                entrada_at__gte=start_utc, entrada_at__lte=end_utc
            )
            .annotate(local_dt=local_dt)
            .annotate(month_key=month_key)
            .values("month_key")
            .annotate(c=Count("pk"))
            .order_by("month_key")
        )

        months = OrderedDict()
        cursor = start_local
        for _ in range(13):
            key = cursor.strftime("%Y-%m")
            months[key] = 0
            cursor = (
                cursor.replace(year=cursor.year + 1, month=1)
                if cursor.month == 12
                else cursor.replace(month=cursor.month + 1)
            )

        for row in qs:
            key = row["month_key"]
            if key in months:
                months[key] = row["c"]

        return JsonResponse(
            {
                "ok": True,
                "labels": list(months.keys()),
                "values": list(months.values()),
            }
        )
    except Exception as e:
        print("[dashboard.api_monthly] ERROR:", e)
        return JsonResponse({"ok": False, "message": str(e)}, status=500)


# ---------------- API: Top guardias ----------------
@db_role_required("Guardia", "Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def api_top_guards(request):
    try:
        days = int(request.GET.get("days", 30))
        limit = int(request.GET.get("limit", 10))

        now_local = datetime.now(dt_tz.utc).astimezone(CL_TZ)
        start_local = now_local - timedelta(days=days - 1)
        _, _, start_utc, _ = _day_bounds_local(start_local)
        _, _, _, end_utc = _today_bounds_local()

        qs = (
            Visita.objects.filter(
                entrada_at__gte=start_utc,
                entrada_at__lt=end_utc,
                operador_entrada__isnull=False,
            )
            .values("operador_entrada_id", "operador_entrada__nombre")
            .annotate(c=Count("pk"))
            .order_by("-c")[:limit]
        )

        labels, values = [], []
        for r in qs:
            nombre = r.get("operador_entrada__nombre")
            user_id = r.get("operador_entrada_id")
            label = (
                nombre.strip()
                if nombre
                else f"Guardia {user_id}"
            )
            labels.append(label)
            values.append(r["c"])

        return JsonResponse(
            {
                "ok": True,
                "labels": labels,
                "values": values,
                "meta": {"days": days, "limit": limit},
            }
        )
    except Exception as e:
        print("[dashboard.api_top_guards] ERROR:", e)
        return JsonResponse({"ok": False, "message": str(e)}, status=500)


# ---------------- Helper CSV ----------------
def _csv_response(filename):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("\ufeff")
    resp.write("sep=;\n")
    return resp


# ---------------- Exportación global de visitas ----------------
@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv(request):
    start_s = request.GET.get("start")
    end_s = request.GET.get("end")

    qs = (
        Visita.objects.select_related(
            "persona", "lugar", "operador_entrada"
        ).order_by("-entrada_at")
    )

    if start_s:
        y, m, d = map(int, start_s.split("-"))
        start_local = datetime(y, m, d, 0, 0, 0, tzinfo=CL_TZ)
        qs = qs.filter(
            entrada_at__gte=start_local.astimezone(dt_tz.utc)
        )

    if end_s:
        y, m, d = map(int, end_s.split("-"))
        end_local = datetime(y, m, d, 23, 59, 59, tzinfo=CL_TZ)
        qs = qs.filter(
            entrada_at__lte=end_local.astimezone(dt_tz.utc)
        )

    lugar_name = (request.GET.get("lugar") or "").strip()
    guardia_name = (request.GET.get("guardia") or "").strip()
    if lugar_name:
        qs = qs.filter(
            lugar__nombre_lugar__icontains=lugar_name
        )
    if guardia_name:
        qs = qs.filter(
            operador_entrada__nombre__icontains=guardia_name
        )

    resp = _csv_response(
        f"visitas_{start_s or 'all'}_{end_s or 'all'}.csv"
    )
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(
        [
            "RUN",
            "Nombre",
            "Lugar",
            "Guardia (entrada)",
            "Entrada (local)",
            "Salida (local)",
        ]
    )

    for v in qs:
        run = getattr(v.persona, "run", "")
        nombres = (getattr(v.persona, "nombres", "") or "").strip()
        apellidos = (getattr(v.persona, "apellidos", "") or "").strip()
        nombre_completo = (
            f"{nombres} {apellidos}".strip()
            or nombres
            or apellidos
        )
        lugar = getattr(v.lugar, "nombre_lugar", "")
        guardia = (
            getattr(v.operador_entrada, "nombre", "")
            if v.operador_entrada
            else ""
        )
        fmt = "%d-%m-%Y %H:%M"
        ent_local = (
            f"'{v.entrada_at.astimezone(CL_TZ).strftime(fmt)}"
            if v.entrada_at
            else ""
        )
        sal_local = (
            f"'{v.salida_at.astimezone(CL_TZ).strftime(fmt)}"
            if v.salida_at
            else ""
        )
        w.writerow(
            [run, nombre_completo, lugar, guardia, ent_local, sal_local]
        )

    return resp


# ---------------- CSV por gráfico (botones) ----------------
@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_14d(request):
    labels, values = [], []
    for i in range(13, -1, -1):
        loc = datetime.now(CL_TZ) - timedelta(days=i)
        d0_local, _, d0_utc, d1_utc = _day_bounds_local(loc)
        c = Visita.objects.filter(
            entrada_at__gte=d0_utc, entrada_at__lt=d1_utc
        ).count()
        labels.append(d0_local.strftime("%d-%m-%Y"))
        values.append(c)

    resp = _csv_response("entradas_14_dias.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["Día", "Entradas"])
    for d, v in zip(labels, values):
        w.writerow([d, v])
    return resp


@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_hour_today(request):
    _, _, start_utc, end_utc = _today_bounds_local()
    q = (
        Visita.objects.filter(
            entrada_at__gte=start_utc, entrada_at__lt=end_utc
        )
        .annotate(h=TruncHour("entrada_at", tzinfo=dt_tz.utc))
        .values("h")
        .annotate(c=Count("h"))
        .order_by("h")
    )
    vals = {h: 0 for h in range(24)}
    for row in q:
        h_utc = row["h"]
        h_local = h_utc.astimezone(CL_TZ).hour
        vals[h_local] += row["c"]

    resp = _csv_response("entradas_por_hora_hoy.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["Hora", "Entradas"])
    for h in range(24):
        w.writerow([f"{h:02d}:00", vals[h]])
    return resp


@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_location_today(request):
    _, _, start_utc, end_utc = _today_bounds_local()
    q = (
        Visita.objects.filter(
            entrada_at__gte=start_utc, entrada_at__lt=end_utc
        )
        .annotate(loc=F("lugar__nombre_lugar"))
        .values("loc")
        .annotate(c=Count("loc"))
        .order_by("-c")
    )

    resp = _csv_response("entradas_por_ubicacion_hoy.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["Ubicación", "Entradas"])
    for r in q:
        w.writerow([r["loc"], r["c"]])
    return resp


@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_top_visitors_week(request):
    _, _, today_start_utc, today_end_utc = _today_bounds_local()
    week_start_local = (
        datetime.now(CL_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        - timedelta(days=6)
    )
    _, _, week_start_utc, _ = _day_bounds_local(week_start_local)
    q = (
        Visita.objects.filter(
            entrada_at__gte=week_start_utc,
            entrada_at__lt=today_end_utc,
        )
        .annotate(doc=F("persona__run"))
        .values("doc")
        .annotate(c=Count("doc"))
        .order_by("-c")[:10]
    )

    resp = _csv_response("top_visitantes_7_dias.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["RUN", "Visitas"])
    for r in q:
        w.writerow([r["doc"], r["c"]])
    return resp


@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_monthly(request):
    now_local = datetime.now(CL_TZ)
    current_month_local = now_local.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    start_local = (current_month_local - timedelta(days=365)).replace(
        day=1
    )
    start_utc = start_local.astimezone(dt_tz.utc)
    end_utc = now_local.astimezone(dt_tz.utc)

    local_dt = ExpressionWrapper(
        F("entrada_at") + timedelta(hours=-3),
        output_field=DateTimeField(),
    )
    month_key = Func(
        local_dt,
        Value("%Y-%m"),
        function="DATE_FORMAT",
        output_field=CharField(),
    )
    qs = (
        Visita.objects.filter(
            entrada_at__gte=start_utc, entrada_at__lte=end_utc
        )
        .annotate(local_dt=local_dt)
        .annotate(month_key=month_key)
        .values("month_key")
        .annotate(c=Count("pk"))
        .order_by("month_key")
    )

    months = OrderedDict()
    cursor = start_local
    for _ in range(13):
        key = cursor.strftime("%Y-%m")
        months[key] = 0
        cursor = (
            cursor.replace(year=cursor.year + 1, month=1)
            if cursor.month == 12
            else cursor.replace(month=cursor.month + 1)
        )
    for row in qs:
        months[row["month_key"]] = row["c"]

    resp = _csv_response("entradas_por_mes.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["Mes (YYYY-MM)", "Entradas"])
    for k, v in months.items():
        w.writerow([k, v])
    return resp


@db_role_required("Jefe de seguridad", "Administrador")
@require_http_methods(["GET"])
def export_csv_top_guards(request):
    days = int(request.GET.get("days", 30))
    limit = int(request.GET.get("limit", 10))

    now_local = datetime.now(CL_TZ)
    start_local = now_local - timedelta(days=days - 1)
    _, _, start_utc, _ = _day_bounds_local(start_local)
    _, _, _, end_utc = _today_bounds_local()

    qs = (
        Visita.objects.filter(
            entrada_at__gte=start_utc,
            entrada_at__lt=end_utc,
            operador_entrada__isnull=False,
        )
        .values("operador_entrada__nombre")
        .annotate(c=Count("pk"))
        .order_by("-c")[:limit]
    )

    resp = _csv_response(f"top_guardias_{days}d.csv")
    w = csv.writer(resp, delimiter=";", lineterminator="\n")
    w.writerow(["Guardia", "Visitas", "Rango (días)"])
    for r in qs:
        w.writerow([r["operador_entrada__nombre"] or "", r["c"], days])
    return resp
