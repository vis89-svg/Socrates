from django.db import models
from django.conf import settings


class UserFile(models.Model):
    FILE_TYPES = (
        ('pdf', 'PDF'),
        ('image', 'Image'),
        ('doc', 'Document'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/')
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    original_name = models.CharField(max_length=500)
    extracted_text = models.TextField(blank=True, null=True)
    conversation = models.ForeignKey('chat.Conversation', on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_name
