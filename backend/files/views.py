from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from .models import UserFile
from .serializers import FileUploadSerializer, FileSerializer
from .parsers import extract_text


class FileUploadView(generics.CreateAPIView):
    serializer_class = FileUploadSerializer
    parser_classes = (MultiPartParser, FormParser)

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        file_path = instance.file.path
        if file_path and instance.file_type == 'pdf':
            text = extract_text(file_path, instance.file_type)
            if text:
                instance.extracted_text = text
                instance.save(update_fields=['extracted_text'])


class FileDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FileSerializer

    def get_queryset(self):
        return UserFile.objects.filter(user=self.request.user)


class FileTextView(generics.RetrieveAPIView):
    serializer_class = FileSerializer

    def get_queryset(self):
        return UserFile.objects.filter(user=self.request.user)
