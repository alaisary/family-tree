from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('tree.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    from django.views.static import serve as media_serve
    urlpatterns += [
        path('media/<path:path>', media_serve, {'document_root': settings.MEDIA_ROOT}),
    ]
