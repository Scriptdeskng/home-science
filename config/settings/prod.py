from .base import *


DEBUG = True

# ALLOWED_HOSTS = []
ALLOWED_HOSTS = ["*"]


# INSTALLED_APPS += ["debug_toolbar"]

# MIDDLEWARE += [
#     "debug_toolbar.middleware.DebugToolbarMiddleware",
# ]

# DEBUG_TOOLBAR_PANELS = [
#     "debug_toolbar.panels.versions.VersionsPanel",
#     "debug_toolbar.panels.timer.TimerPanel",
#     "debug_toolbar.panels.settings.SettingsPanel",
#     "debug_toolbar.panels.headers.HeadersPanel",
#     "debug_toolbar.panels.request.RequestPanel",
#     "debug_toolbar.panels.sql.SQLPanel",
#     "debug_toolbar.panels.staticfiles.StaticFilesPanel",
#     "debug_toolbar.panels.templates.TemplatesPanel",
#     "debug_toolbar.panels.cache.CachePanel",
#     "debug_toolbar.panels.signals.SignalsPanel",
#     "debug_toolbar.panels.logging.LoggingPanel",
#     "debug_toolbar.panels.redirects.RedirectsPanel",
# ]


# def show_toolbar(request):
#     return True


# DEBUG_TOOLBAR_CONFIG = {
#     "INTERCEPT_REDIRECTS": False,
#     "SHOW_TOOLBAR_CALLBACK": show_toolbar,
# }


# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": BASE_DIR / "db2.sqlite3",
#     }
# }


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": "5432",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True


AUTO_MAIL_FROM = config("AUTO_MAIL_FROM", "dev@rainfall.ng")

DEFAULT_FROM_EMAIL = "dev@rainfall.ng"

EMAIL_SUBJECT_PREFIX = ["HomeScience"]

EMAIL_TIMEOUT = 360


EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")


ADMINS = (("HomeScience Support", "hello@zamari.tv"),)


# CELERY related settings
BROKER_URL = "amqp://localhost"
# CELERY_RESULT_BACKEND = 'amqp://'
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"


# AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")

# AWS_S3_FILE_OVERWRITE = False
# AWS_DEFAULT_ACL = None
# AWS_S3_REGION_NAME = "us-east-1"
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"


DO_SPACES_ACCESS_KEY_ID = config("DO_SPACE_ACCESS_KEY")
DO_SPACES_SECRET_ACCESS_KEY = config("DO_SPACE_SECRET_KEY")
DO_SPACES_BUCKET_NAME = "homescience-files"
DO_SPACES_REGION_NAME = "nyc3"
DO_SPACES_ENDPOINT_URL = "https://nyc3.digitaloceanspaces.com"


AWS_ACCESS_KEY_ID = DO_SPACES_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = DO_SPACES_SECRET_ACCESS_KEY
AWS_STORAGE_BUCKET_NAME = DO_SPACES_BUCKET_NAME
AWS_S3_REGION_NAME = DO_SPACES_REGION_NAME
AWS_S3_ENDPOINT_URL = DO_SPACES_ENDPOINT_URL
AWS_S3_SIGNATURE_VERSION = "s3v4"
# AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.nyc3.digitaloceanspaces.com"

AWS_S3_CUSTOM_DOMAIN = (
    f"{DO_SPACES_BUCKET_NAME}.{DO_SPACES_REGION_NAME}.digitaloceanspaces.com"
)

AWS_DEFAULT_ACL = "public-read"

# Ensure file paths are correct
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

DEFAULT_FILE_STORAGE = "homescience.settings.storage_backends.MediaStorage"
