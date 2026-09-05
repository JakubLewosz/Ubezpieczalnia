from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from common.api import Conflict
from common.audit import record
from common.models import AuditEvent
from common.normalization import normalize
from common.query import positive_ids
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = Client.objects.all()
        excluded = positive_ids(self.request.query_params.get("exclude"), "exclude")
        if excluded:
            qs = qs.exclude(pk__in=excluded)
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false")
            if archived != "all":
                qs = qs.filter(archived=archived == "true")
        search = normalize(self.request.query_params.get("search", ""))
        if search:
            qs = qs.filter(
                Q(search_text__contains=search) | Q(policy_roles__policy__search_text__contains=search)
            ).distinct()
        ordering = self.request.query_params.get("ordering", "display_name")
        return qs.order_by(
            ordering
            if ordering in ["display_name", "-display_name", "created_at", "-created_at"]
            else "display_name",
            "id",
        )

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                client = serializer.save(version=1)
                record(self.request.user, "client.created", "client", client.pk, client.pk)
        except IntegrityError:
            raise Conflict(
                "Kartoteka z tym samym PESEL/NIP już istnieje, również w archiwum. Sprawdź ją; dane nie zostały scalone."
            )

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            obj = self.get_queryset().select_for_update().get(pk=self.get_object().pk)
            if request.data.get("version") != obj.version:
                raise Conflict()
            serializer = self.get_serializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            try:
                with transaction.atomic():
                    serializer.save(version=obj.version + 1)
            except IntegrityError:
                raise Conflict("Kartoteka z tym samym PESEL/NIP już istnieje.")
            record(
                request.user,
                "client.archived" if obj.archived else "client.updated",
                "client",
                obj.pk,
                obj.pk,
            )
            return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        client = self.get_object()
        events = AuditEvent.objects.filter(client=client).select_related("actor")[:100]
        return Response(
            [
                {
                    "id": event.pk,
                    "action": event.action,
                    "actor_name": event.actor.username if event.actor else "Usunięte konto",
                    "created_at": event.created_at,
                    "object_type": event.object_type,
                    "object_id": event.object_id,
                }
                for event in events
            ]
        )
