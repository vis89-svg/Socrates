from django.shortcuts import get_object_or_404
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count, OuterRef, Subquery
import uuid
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer, ConversationListSerializer, MessageSerializer
from .export_service import ExportService


class ConversationListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ConversationListSerializer
        return ConversationSerializer

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).annotate(
            _last_message=Subquery(
                Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at').values('content')[:1]
            ),
            _message_count=Count('messages'),
        )

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


class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessageSerializer
    lookup_url_kwarg = 'message_pk'

    def get_queryset(self):
        conv = get_object_or_404(Conversation, id=self.kwargs['pk'], user=self.request.user)
        return Message.objects.filter(conversation=conv)

    def perform_update(self, serializer):
        instance = serializer.save()
        Message.objects.filter(
            conversation_id=self.kwargs['pk'],
            created_at__gt=instance.created_at,
        ).delete()


class MessageExportView(APIView):
    def post(self, request, pk, message_pk):
        conv = get_object_or_404(Conversation, id=pk, user=request.user)
        message = get_object_or_404(Message, conversation=conv, id=message_pk)
        fmt = request.data.get('format', 'docx')
        if fmt not in ('docx', 'pdf'):
            return Response({'error': 'format must be docx or pdf'}, status=status.HTTP_400_BAD_REQUEST)

        content = message.content
        if fmt == 'docx':
            buf = ExportService.to_docx(content)
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            filename = f'socrates-{conv.id}-{message.id}.docx'
        else:
            buf = ExportService.to_pdf(content)
            media_type = 'application/pdf'
            filename = f'socrates-{conv.id}-{message.id}.pdf'

        response = HttpResponse(buf.getvalue(), content_type=media_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ConversationShareView(APIView):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, id=pk, user=request.user)
        if not conv.share_token:
            conv.share_token = uuid.uuid4()
            conv.share_created_at = timezone.now()
            conv.save(update_fields=['share_token', 'share_created_at'])
        base = getattr(settings, 'PUBLIC_BASE_URL', 'http://localhost:8000')
        return Response({
            'share_url': f'{base}/share/{conv.share_token}/',
            'share_token': str(conv.share_token),
        })

    def delete(self, request, pk):
        conv = get_object_or_404(Conversation, id=pk, user=request.user)
        conv.share_token = None
        conv.share_created_at = None
        conv.save(update_fields=['share_token', 'share_created_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicShareView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        conv = get_object_or_404(Conversation, share_token=token)
        messages = Message.objects.filter(conversation=conv).values('role', 'content', 'created_at')
        return Response({
            'title': conv.title or f'Conversation {conv.id}',
            'shared_at': conv.share_created_at,
            'messages': list(messages),
        })


class SharePageView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        conv = get_object_or_404(Conversation, share_token=token)
        messages = Message.objects.filter(conversation=conv).order_by('created_at')
        rows = ''.join(
            f'<div class="msg {m.role}"><div class="bubble">{m.content}</div></div>'
            for m in messages
        )
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Shared Chat — Owl</title>'
            '<style>'
            'body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#fdf6ec;margin:0;padding:1.5rem;color:#3a2a1a;}'
            '.wrap{max-width:760px;margin:0 auto;}'
            '.brand{display:flex;align-items:center;gap:0.5rem;font-weight:800;font-size:1.3rem;}'
            '.brand .dot{color:#e08a2e;}'
            'h1{font-size:1.2rem;margin:0.8rem 0 1.2rem;}'
            '.msg{margin:0.6rem 0;display:flex;}'
            '.msg.user{justify-content:flex-end;}'
            '.bubble{max-width:80%;padding:0.7rem 1rem;border-radius:16px;background:#fff;white-space:pre-wrap;word-break:break-word;box-shadow:0 2px 8px rgba(90,60,25,0.08);}'
            '.msg.user .bubble{background:linear-gradient(135deg,#e08a2e,#d97706);color:#fff;}'
            '.msg.system .bubble{background:#fff3cd;margin:0 auto;text-align:center;}'
            'table{border-collapse:collapse;width:100%;margin:0.4rem 0;}'
            'td,th{border:1px solid #e5d5ba;padding:0.3rem 0.5rem;}'
            '.foot{color:#9a8a74;font-size:0.8rem;margin-top:1.5rem;text-align:center;}'
            '</style></head><body><div class="wrap">'
            '<div class="brand">🦉 Owl<span class="dot">.</span></div>'
            f'<h1>Shared conversation: {conv.title or "Untitled"}</h1>'
            f'<div>{rows}</div>'
            '<p class="foot">Shared via Owl</p>'
            '</div></body></html>'
        )
        return HttpResponse(html, content_type='text/html; charset=utf-8')


class StreamView(APIView):
    def post(self, request, pk):
        conv = get_object_or_404(Conversation, id=pk, user=request.user)
        user_message = request.data.get('message', '')
        file_ids = request.data.get('file_ids', [])
        web_search = request.data.get('web_search', None)
        regenerate_id = request.data.get('regenerate_message_id', None)
        if not user_message and not file_ids and not regenerate_id:
            return Response({'error': 'message or file is required'}, status=status.HTTP_400_BAD_REQUEST)

        files_data = []
        if file_ids:
            from files.models import UserFile
            files = UserFile.objects.filter(id__in=file_ids, user=request.user, conversation=conv)
            for f in files:
                info = {'name': f.original_name, 'type': f.file_type}
                if f.extracted_text:
                    text = f.extracted_text
                    if len(text) > 5000:
                        text = text[:5000] + '\n...[truncated]'
                    info['text'] = text
                files_data.append(info)

        if regenerate_id:
            target = Message.objects.filter(id=regenerate_id, conversation=conv, role='user').first()
            if not target:
                return Response({'error': 'message not found'}, status=status.HTTP_404_NOT_FOUND)
            user_message = target.content
        else:
            content = user_message
            if files_data:
                file_refs = ', '.join(f'[{f["name"]}]' for f in files_data)
                content = f'{user_message}\n[Attached files: {file_refs}]' if user_message else f'[Attached files: {file_refs}]'

            Message.objects.create(conversation=conv, role='user', content=content)

        from ai.orchestrator import generateResponse
        from django.http import StreamingHttpResponse
        import json

        history = list(Message.objects.filter(conversation=conv).values('role', 'content'))

        def event_stream():
            full_response = ''
            for event in generateResponse(user_message, history, user=request.user, conversation_id=conv.id, files_data=files_data, web_search=web_search):
                if event['type'] == 'analysis':
                    yield f'data: {json.dumps({"analysis": event["capabilities"]})}\n\n'
                elif event['type'] == 'token':
                    full_response += event['content']
                    yield f'data: {json.dumps({"token": event["content"]})}\n\n'
                elif event['type'] == 'search_results':
                    yield f'data: {json.dumps({"search": True, "count": event["count"], "provider": event["provider"], "evidence": event.get("evidence", []), "intent": event.get("intent"), "coverage": event.get("coverage")})}\n\n'
                elif event['type'] == 'tool_use':
                    yield f'data: {json.dumps({"tool_use": {"tool": event["tool"], "label": event.get("label", ""), "args": event.get("args", {})}})}\n\n'
                elif event['type'] == 'stage':
                    yield f'data: {json.dumps({"stage": event["label"]})}\n\n'
                elif event['type'] == 'citations':
                    yield f'data: {json.dumps({"citations": event["citations"]})}\n\n'
                elif event['type'] == 'research_summary':
                    yield f'data: {json.dumps({"summary": event["summary"]})}\n\n'
                elif event['type'] == 'timings':
                    yield f'data: {json.dumps({"timings": event["timings"]})}\n\n'
                elif event['type'] == 'done':
                    saved = Message.objects.create(conversation=conv, role='assistant', content=full_response)
                    yield f'data: {json.dumps({"done": True, "message_id": saved.id})}\n\n'

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
