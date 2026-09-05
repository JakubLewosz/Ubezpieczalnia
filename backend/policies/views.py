from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from common.api import Conflict
from common.audit import record
from common.normalization import normalize
from common.query import positive_ids
from .models import Policy
from .serializers import PolicySerializer


def expiring(qs, days):
    today = timezone.localdate()
    return qs.filter(archived=False, end_date__gte=today, end_date__lte=today + timedelta(days=days))


class PolicyViewSet(viewsets.ModelViewSet):
    serializer_class = PolicySerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Policy.objects.prefetch_related("participants__client", "documents")
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false")
            if archived != "all":
                qs = qs.filter(archived=archived == "true")
        clients = positive_ids(self.request.query_params.get("client"), "client", limit=1)
        if clients:
            qs = qs.filter(participants__client_id=clients[0]).distinct()
        days = self.request.query_params.get("expires_in")
        if days:
            if not days.isdigit() or not 0 <= int(days) <= 365:
                raise ValidationError("Zakres terminów musi wynosić 0–365 dni.")
            qs = expiring(qs, int(days))
        search = normalize(self.request.query_params.get("search", ""))
        if search:
            qs = qs.filter(search_text__contains=search)
        ordering = self.request.query_params.get("ordering", "end_date")
        return qs.order_by(ordering if ordering in {"end_date", "-end_date", "number", "-number"}
                           else "end_date", "id")

    def perform_create(self, serializer):
        with transaction.atomic():
            obj = serializer.save(version=1)
            self._audit(obj, "policy.created")

    def _audit(self, obj, action, previous_client_ids=()):
        affected = set(previous_client_ids) | set(obj.participants.values_list("client_id", flat=True))
        for client_id in affected:
            record(self.request.user, action, "policy", obj.pk, client_id)

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            obj = Policy.objects.select_for_update().get(pk=self.get_object().pk)
            if request.data.get("version") != obj.version:
                raise Conflict()
            previous_client_ids = list(obj.participants.values_list("client_id", flat=True))
            serializer = self.get_serializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save(version=obj.version + 1)
            self._audit(obj, "policy.archived" if obj.archived else "policy.updated", previous_client_ids)
            return Response(serializer.data)
