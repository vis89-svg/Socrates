from memory.models import Memory


def get_relevant_memories(user, query, max_results=5):
    return Memory.objects.filter(user=user).search(query)[:max_results]
