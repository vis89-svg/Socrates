from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.GenerateView.as_view(), name='ai-generate'),
    path('stream/', views.StreamView.as_view(), name='ai-stream'),
    path('debug/trace/<str:request_id>/', views.TraceView.as_view(), name='ai-trace'),
]
