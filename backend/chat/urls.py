from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.ConversationListCreateView.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:pk>/messages/', views.MessageListCreateView.as_view(), name='message-list'),
    path('conversations/<int:pk>/stream/', views.StreamView.as_view(), name='message-stream'),
]
