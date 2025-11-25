from django.urls import path
from .views import *

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),
    # APIs
    path("api/summary/", api_summary, name="dashboard_api_summary"),
    path("api/monthly/", api_monthly, name="dashboard_api_monthly"),
    path("api/top_guardias/", api_top_guards, name="dashboard_api_top_guards"),

    # Export global
    path("export/csv/", export_csv, name="dashboard_export_csv"),

    # Export por gráfico
    path("export/csv/14d/", export_csv_14d, name="dashboard_export_csv_14d"),
    path("export/csv/hour_today/", export_csv_hour_today, name="dashboard_export_csv_hour_today"),
    path("export/csv/location_today/", export_csv_location_today, name="dashboard_export_csv_location_today"),
    path("export/csv/top_visitors_week/", export_csv_top_visitors_week, name="dashboard_export_csv_top_visitors_week"),
    path("export/csv/monthly/", export_csv_monthly, name="dashboard_export_csv_monthly"),
    path("export/csv/top_guards/", export_csv_top_guards, name="dashboard_export_csv_top_guards"),
]
