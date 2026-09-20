from django.conf import settings


def site_context(request):
    """Expose the configurable site name to every template."""
    return {'site_name': settings.SITE_NAME}
