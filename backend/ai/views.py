from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .inference import generate_stream
from .prompt_builder import build_prompt
from .memory_retriever import get_relevant_memories


class GenerateView(APIView):
    def post(self, request):
        message = request.data.get('message', '')
        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        memories = get_relevant_memories(request.user, message)
        prompt = build_prompt(message, memories=memories)
        response_text = ''.join(generate_stream(prompt))
        return Response({'response': response_text})


class StreamView(APIView):
    def post(self, request):
        message = request.data.get('message', '')
        if not message:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        memories = get_relevant_memories(request.user, message)
        prompt = build_prompt(message, memories=memories)

        from django.http import StreamingHttpResponse
        import json

        def event_stream():
            for token in generate_stream(prompt):
                yield f'data: {json.dumps({"token": token})}\n\n'
            yield f'data: {json.dumps({"done": True})}\n\n'

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
