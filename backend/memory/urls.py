from django.urls import path
from . import views

urlpatterns = [
    path('memories/', views.MemoryListCreateView.as_view(), name='memory-list'),
    path('memories/<int:pk>/', views.MemoryDetailView.as_view(), name='memory-detail'),
]
