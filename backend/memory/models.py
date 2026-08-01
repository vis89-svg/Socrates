from django.db import models
from django.conf import settings
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank


class MemoryQuerySet(models.QuerySet):
    def search(self, query):
        vector = SearchVector('key', 'content', config='english')
        search_query = SearchQuery(query, config='english')
        return self.annotate(
            rank=SearchRank(vector, search_query)
        ).filter(rank__gte=0.01).order_by('-rank', '-importance')


class Memory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memories')
    key = models.CharField(max_length=255)
    content = models.TextField()
    importance = models.FloatField(default=0.5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MemoryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = 'memories'
        ordering = ['-importance', '-updated_at']

    def __str__(self):
        return self.key


class ConversationSummary(models.Model):
    conversation = models.ForeignKey('chat.Conversation', on_delete=models.CASCADE, related_name='summaries')
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Summary of conversation {self.conversation_id}'
