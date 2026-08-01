from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from chat.views import SharePageView, PublicShareView
from config.views import frontend

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/ai/', include('ai.urls')),
    path('api/memory/', include('memory.urls')),
    path('api/files/', include('files.urls')),
    path('share/<uuid:token>/', SharePageView.as_view(), name='share-page'),
    path('api/share/<uuid:token>/', PublicShareView.as_view(), name='share-api'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.FRONTEND_ENABLED:
    urlpatterns += [
        re_path(r'^(?!api/|share/|admin/|uploads/)(?P<path>.*)$', frontend, name='frontend'),
    ]
