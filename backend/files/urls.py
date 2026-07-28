from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.FileUploadView.as_view(), name='file-upload'),
    path('files/<int:pk>/', views.FileDetailView.as_view(), name='file-detail'),
    path('files/<int:pk>/text/', views.FileTextView.as_view(), name='file-text'),
]
