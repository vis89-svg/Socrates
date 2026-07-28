from rest_framework import serializers
from .models import UserFile


class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFile
        fields = ('id', 'file', 'file_type', 'original_name', 'extracted_text', 'conversation', 'uploaded_at')
        read_only_fields = ('id', 'extracted_text', 'uploaded_at')


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFile
        fields = ('id', 'file_type', 'original_name', 'extracted_text', 'conversation', 'uploaded_at')
        read_only_fields = ('id', 'uploaded_at')
