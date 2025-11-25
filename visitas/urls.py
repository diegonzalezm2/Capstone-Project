from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

# Importamos directamente las vistas para usar los nombres de función
from .views import *

urlpatterns = [
    # Escáner
    path('', scan_view, name='scan'),
    path('api/scan/', scan_api, name='scan_api'),

    # Ingreso manual
    path('manual/', manual_view, name='visitas_manual'),
    path('api/manual/', manual_api, name='manual_api'),

    # Listado de visitas
    path('listado/', visitas_list_view, name='visitas_list'),
    path('api/list/', visitas_list_api, name='visitas_list_api'),
    path('api/close/', visita_close_api, name='visita_close_api'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
