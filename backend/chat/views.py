from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer


class ConversationListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ConversationListSerializer
        return ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ConversationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)


class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer

    def get_queryset(self):
        conv = get_object_or_404(Conversation, id=self.kwargs['pk'], user=self.request.user)
        return Message.objects.filter(conversation=conv)

    def perform_create(self, serializer):
        conv = get_object_or_404(Conversation, id=self.kwargs['pk'], user=self.request.user)
        serializer.save(conversation=conv)


class StreamView(APIView):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, id=pk, user=request.user)
        user_message = request.data.get('message', '')
        if not user_message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        Message.objects.create(conversation=conv, role='user', content=user_message)

        from ai.inference import generate_stream
        from ai.prompt_builder import build_prompt
        from ai.memory_retriever import get_relevant_memories

        memories = get_relevant_memories(request.user, user_message)
        history = list(Message.objects.filter(conversation=conv).values('role', 'content'))
        prompt = build_prompt(user_message, history, memories)

        from django.http import StreamingHttpResponse
        import json

        def event_stream():
            full_response = ''
            for token in generate_stream(prompt):
                full_response += token
                yield f'data: {json.dumps({"token": token})}\n\n'
            Message.objects.create(conversation=conv, role='assistant', content=full_response)
            yield f'data: {json.dumps({"done": True})}\n\n'

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
