from django.urls import path
from . import views

urlpatterns = [
    path('conversations/', views.ConversationListCreateView.as_view(), name='conversation-list'),
    path('conversations/<int:pk>/', views.ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:pk>/messages/', views.MessageListCreateView.as_view(), name='message-list'),
    path('conversations/<int:pk>/stream/', views.StreamView.as_view(), name='message-stream'),
    path('conversations/<int:pk>/messages/<int:message_pk>/', views.MessageDetailView.as_view(), name='message-detail'),
    path('conversations/<int:pk>/messages/<int:message_pk>/export/', views.MessageExportView.as_view(), name='message-export'),
    path('conversations/<int:pk>/share/', views.ConversationShareView.as_view(), name='conversation-share'),
]
