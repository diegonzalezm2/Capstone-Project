from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from .views import *

urlpatterns = [
    path('',login_view,name="login"),
    path('logout/confirm/',logout_confirm, name='logout_confirm'),
    path('logout/', logout_view, name='logout'),

    # administración de usuarios
    path("usuarios/", users_list, name="accounts_users_list"),
    path("usuarios/nuevo/", users_create, name="accounts_users_create"),
    path("usuarios/<int:user_id>/editar/", users_edit, name="accounts_users_edit"),
    path("usuarios/<int:user_id>/toggle/", users_toggle_authorized, name="accounts_users_toggle"),
    path("accounts/usuarios/<int:user_id>/eliminar/", users_delete, name="accounts_users_delete"),
    path("_reauth/", reautorizar_por_email, name="reauth_temp"),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG == True:
    urlpatterns += static(settings.STATIC_URL,document_root=settings.STATIC_ROOT)