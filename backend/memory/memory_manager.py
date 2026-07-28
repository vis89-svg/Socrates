from .models import Memory, ConversationSummary


def add_memory(user, key, content, importance=0.5):
    return Memory.objects.create(user=user, key=key, content=content, importance=importance)


def get_summary(conversation):
    return ConversationSummary.objects.filter(conversation=conversation).first()
