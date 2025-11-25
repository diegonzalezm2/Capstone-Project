"""
Django settings for visitasegura project.
"""

from pathlib import Path
from os.path import join
import environ

# =========================
# Paths & Env
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))

# Hacer opcional la carga del .env (en Railway puedes usar solo variables de entorno)
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# Dominio actual de Railway (puedes cambiarlo si Railway te asigna uno nuevo)
RAILWAY_DOMAIN = "capstone-project-production-6b24.up.railway.app"

# =========================
# Seguridad / Debug
# =========================
SECRET_KEY = env("SECRET_KEY", default="!!!-dev-unsafe-key-change-me-!!!")
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    RAILWAY_DOMAIN,
]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    f"https://{RAILWAY_DOMAIN}",
]

# =========================
# Apps
# =========================
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Proyecto
    "dashboard",
    "lugares",
    "personas",
    "visitas",
    "accounts.apps.AccountsConfig",

    # Allauth
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

SITE_ID = 1

# =========================
# Middleware
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise para servir archivos estáticos en producción
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    # DEBE ir antes que uses messages en tu middleware
    "django.contrib.messages.middleware.MessageMiddleware",

    # Tu middleware de autorización (va DESPUÉS de MessageMiddleware)
    "accounts.middleware.RequireAuthorizedMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# =========================
# URLs / Templates / WSGI
# =========================
ROOT_URLCONF = "visitasegura.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [join(BASE_DIR, "plantillas")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.ui_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "visitasegura.wsgi.application"

# =========================
# Base de Datos (MySQL)
# =========================
DB_NAME = env("DB_NAME", default=env("MYSQL_DATABASE", default="visita_segura"))
DB_USER = env("DB_USER", default=env("MYSQLUSER", default="root"))
DB_PASSWORD = env("DB_PASSWORD", default=env("MYSQLPASSWORD", default=""))
DB_HOST = env("DB_HOST", default=env("MYSQLHOST", default="127.0.0.1"))
DB_PORT = env.int("DB_PORT", default=env.int("MYSQLPORT", default=3306))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# =========================
# Password validators
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# i18n / Zona horaria
# =========================
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# =========================
# Archivos estáticos / media
# =========================
STATIC_URL = "static/"

STATICFILES_DIRS = [join(BASE_DIR, "assets")]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Auth / Redirects
# =========================
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "Principal"
LOGOUT_REDIRECT_URL = "Principal"
ACCOUNT_LOGOUT_REDIRECT_URL = LOGOUT_REDIRECT_URL

# =========================
# Allauth: Backends
# =========================
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# =========================
# Allauth: Config general
# =========================
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True

ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAccountAdapter"

# =========================
# Allauth: Google
# =========================
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID"),
            "secret": env("GOOGLE_SECRET"),
            "key": "",
        },
        "SCOPE": ["email", "profile"],
    }
}

# =========================
# Auto-provisión
# =========================
AUTO_PROVISION_OPERADOR = env.bool("AUTO_PROVISION_OPERADOR", default=True)
OPERADOR_DEFAULT_ROL_ID = env.int("OPERADOR_DEFAULT_ROL_ID", default=1)
