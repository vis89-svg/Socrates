from rest_framework import generics
from .models import Memory
from .serializers import MemorySerializer


class MemoryListCreateView(generics.ListCreateAPIView):
    serializer_class = MemorySerializer

    def get_queryset(self):
        qs = Memory.objects.filter(user=self.request.user)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.search(search)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MemoryDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = MemorySerializer

    def get_queryset(self):
        return Memory.objects.filter(user=self.request.user)
