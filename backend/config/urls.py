from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/ai/', include('ai.urls')),
    path('api/memory/', include('memory.urls')),
    path('api/files/', include('files.urls')),
]
