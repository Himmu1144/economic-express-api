import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Explicit runtime environment wins over Neon-generated local files.
load_dotenv(BASE_DIR / ".env.local", override=False)
load_dotenv(BASE_DIR / ".env", override=False)


def flag(name, default=False):
    return os.environ.get(name, str(default)).lower() == "true"


def csv(name):
    return [s.strip() for s in os.environ.get(name, "").split(",") if s.strip()]


DEBUG = flag("DEBUG")
TESTING = flag("TESTING")
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = csv("ALLOWED_HOSTS")
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
DATABASES = {
    "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=60)
}
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
# Neon transaction pooling cannot preserve cursors between transactions.
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
if not TESTING and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("PostgreSQL is required outside tests")
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "storages",
    "tinymce",
    "axes",
    "news.apps.NewsConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation." + x}
    for x in [
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    ]
]
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or os.environ.get(
    "AWS_ENDPOINT_URL_S3"
)
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME") or os.environ.get(
    "AWS_REGION", "auto"
)
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=31536000, immutable"}
CORS_ALLOWED_ORIGINS = csv("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = csv("CSRF_TRUSTED_ORIGINS")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
REVALIDATE_SECRET = os.environ.get("REVALIDATE_SECRET", "")
BREAKING_HOURS = int(os.environ.get("BREAKING_HOURS", "12"))
SECURE_SSL_REDIRECT = flag("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Enable only behind a proxy that strips incoming X-Forwarded-Proto.
if flag("TRUST_PROXY_PROTO"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "NUM_PROXIES": 0,
}
TINYMCE_DEFAULT_CONFIG = {
    "language": "en",  # Built-in English; no missing en_IN language pack request.
    "height": 600,
    "menubar": False,
    "plugins": "lists link image code",
    "toolbar": "undo redo | blocks | bold italic | bullist numlist | link image | code",
    "block_formats": "Paragraph=p; Heading 2=h2; Heading 3=h3",
    "images_upload_url": "/admin/inline-upload/",
    "automatic_uploads": True,
    "images_upload_credentials": True,
    "images_upload_handler": "eeUploadImage",
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
