from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def deployment_settings(app_configs, **kwargs):
    errors = []
    for name in [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_STORAGE_BUCKET_NAME",
        "FRONTEND_URL",
        "REVALIDATE_SECRET",
        "ALLOWED_HOSTS",
        "CORS_ALLOWED_ORIGINS",
        "CSRF_TRUSTED_ORIGINS",
    ]:
        if not getattr(settings, name, None):
            errors.append(
                Error(f"{name} must be configured for launch.", id="news.E001")
            )
    if not settings.AWS_S3_CUSTOM_DOMAIN and not (
        settings.AWS_S3_ENDPOINT_URL or ""
    ).startswith("https://"):
        errors.append(
            Error(
                "Configure an HTTPS storage endpoint or custom image domain.",
                id="news.E005",
            )
        )
    if settings.FRONTEND_URL and not settings.FRONTEND_URL.startswith("https://"):
        errors.append(Error("FRONTEND_URL must use HTTPS.", id="news.E002"))
    if len(settings.REVALIDATE_SECRET) < 32:
        errors.append(
            Error(
                "REVALIDATE_SECRET needs at least 32 random characters.", id="news.E003"
            )
        )
    if settings.TESTING:
        errors.append(Error("TESTING must be False in production.", id="news.E004"))
    return errors
