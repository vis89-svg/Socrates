from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .orchestrator import generateResponse
from django.http import StreamingHttpResponse
from django.conf import settings
from .observability import Observability
from .feature_flags import FeatureFlags
import json


class GenerateView(APIView):
    def post(self, request):
        message = request.data.get('message', '')
        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        response_text = ''
        citations = []
        for event in generateResponse(message, history=None, user=request.user):
            if event['type'] == 'token':
                response_text += event['content']
            elif event['type'] == 'citations':
                citations = event['citations']
            elif event['type'] == 'done':
                response_text = event['response']

        return Response({'response': response_text, 'citations': citations})


class StreamView(APIView):
    def post(self, request):
        message = request.data.get('message', '')
        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        web_search = request.data.get('web_search', None)

        def event_stream():
            for event in generateResponse(message, history=None, user=request.user, web_search=web_search):
                if event['type'] == 'analysis':
                    yield f'data: {json.dumps({"analysis": event["capabilities"]})}\n\n'
                elif event['type'] == 'token':
                    yield f'data: {json.dumps({"token": event["content"]})}\n\n'
                elif event['type'] == 'search_results':
                    yield f'data: {json.dumps({"search": True, "count": event["count"], "provider": event["provider"]})}\n\n'
                elif event['type'] == 'stage':
                    yield f'data: {json.dumps({"stage": event["label"]})}\n\n'
                elif event['type'] == 'citations':
                    yield f'data: {json.dumps({"citations": event["citations"]})}\n\n'
                elif event['type'] == 'done':
                    yield f'data: {json.dumps({"done": True})}\n\n'

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


class TraceView(APIView):
    def get(self, request, request_id):
        if not (settings.DEBUG or FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE')):
            return Response({'error': 'Trace endpoint disabled'}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        trace = Observability.get_trace(request_id)
        if trace is None:
            return Response({'error': 'Trace not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'request_id': request_id, 'stages': trace})
