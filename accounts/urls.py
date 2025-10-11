from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from .views import *

urlpatterns = [
    path('',login_view,name="login"),
    path('logout/confirm/',logout_confirm, name='logout_confirm'),
    path('logout/', logout_view, name='logout'),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG == True:
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)