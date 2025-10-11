from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from .views import *

urlpatterns = [
    path('', scan_view, name='scan'),
    path('api/scan/', scan_api, name='scan_api'),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG == True:
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)