from collections.abc import Mapping
from django.db import transaction
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Value, When
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from accounts.models import User
from common.audit import record
from common.api import Conflict
from common.query import positive_ids
from documents.serializers import DocumentSerializer
from documents.views import private_response
from .config import current_mailbox, load_config, MailConfigurationError
from .models import Attachment, Mailbox, Message, ReadReceipt
from .serializers import EmployeeSerializer, MailboxSerializer, MessageDetailSerializer, MessageSerializer
from .work import ACTIVE, change_work, check_version, linked_objects, require_owner


def message_query(user):
    return Message.objects.select_related("owner", "completed_by", "client", "mailbox").annotate(
        is_read=Exists(ReadReceipt.objects.filter(message=OuterRef("pk"), user=user)),
        attachment_count=Count("attachments"),
        received_sort=Coalesce("received_at", "imported_at"),
    )


class MessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer

    def get_queryset(self):
        qs = message_query(self.request.user)
        if self.action != "list":
            return qs
        p = self.request.query_params
        queue = p.get("queue", "action")
        if queue == "action":
            qs = qs.filter(status__in=ACTIVE)
        elif queue == "unassigned":
            qs = qs.filter(status__in=ACTIVE, owner__isnull=True)
        elif queue == "mine":
            qs = qs.filter(status__in=ACTIVE, owner=self.request.user)
        elif queue != "all":
            raise ValidationError({"queue": "Wybierz action, unassigned, mine lub all."})
        status = p.get("status")
        if status:
            if status not in Message.Status.values:
                raise ValidationError({"status": "Nieznany stan obsługi."})
            qs = qs.filter(status=status)
        for parameter in ("client", "mailbox"):
            ids = positive_ids(p.get(parameter), parameter, limit=1)
            if ids:
                qs = qs.filter(**{f"{parameter}_id": ids[0]})
        query = p.get("search", "").strip()
        if "\x00" in query or len(query) > 200:
            raise ValidationError({"search": "Zapytanie może mieć najwyżej 200 znaków."})
        if query:
            qs = qs.filter(Q(subject__icontains=query) | Q(sender_name__icontains=query) | Q(sender_address__icontains=query))
        ordering = p.get("ordering", "received_at")
        if ordering not in {"received_at", "-received_at"}:
            raise ValidationError({"ordering": "Sortuj po received_at lub -received_at."})
        return qs.order_by(("-" if ordering.startswith("-") else "") + "received_sort", "id")

    def get_serializer_class(self):
        return MessageSerializer if self.action == "list" else MessageDetailSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        counts = {key: queryset.filter(status=key).count() for key in Message.Status.values}
        counts["total"] = queryset.count()
        page = self.paginate_queryset(queryset)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data["counts"] = counts
        return response

    def detail_response(self, pk):
        return Response(MessageDetailSerializer(message_query(self.request.user).get(pk=pk)).data)

    @action(detail=True, methods=["post"], url_path="read")
    def opened(self, request, pk=None):
        obj = self.get_object()
        ReadReceipt.objects.get_or_create(message=obj, user=request.user)
        return Response({"is_read": True})

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        self.get_object()
        change_work(pk, request.user, request.data, claim=True)
        return self.detail_response(pk)

    @action(detail=True, methods=["post"])
    def work(self, request, pk=None):
        self.get_object()
        change_work(pk, request.user, request.data)
        return self.detail_response(pk)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        from common.models import AuditEvent
        obj = self.get_object()
        qs = AuditEvent.objects.filter(object_type="message", object_id=obj.pk).select_related("actor")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([{"id": e.pk, "action": e.action, "actor_name": e.actor.username if e.actor else "Synchronizacja",
                                            "created_at": e.created_at, "metadata": e.metadata} for e in page])

    @action(detail=True, methods=["get"])
    def raw(self, request, pk=None):
        obj = self.get_object()
        if not obj.raw_file:
            raise Http404("Źródło nie zostało pobrane.")
        try:
            handle = obj.raw_file.open("rb")
        except FileNotFoundError:
            raise Http404("Brak źródła w prywatnym magazynie; sprawdź odtworzenie kopii.") from None
        return private_response(handle, "application/octet-stream", f"wiadomosc-{obj.pk}.eml", True)


class AttachmentViewSet(viewsets.GenericViewSet):
    queryset = Attachment.objects.all()

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        obj = self.get_object()
        if obj.blocked_reason or not obj.file:
            raise ValidationError("Załącznik zablokowany; brak aktywnego podglądu ani pobrania tej części.")
        try:
            handle = obj.file.open("rb")
        except FileNotFoundError:
            raise Http404("Brak pliku w magazynie; sprawdź kopię danych.") from None
        name = obj.original_name.replace("\\", "/").split("/")[-1]
        return private_response(handle, "application/octet-stream", name, True)

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        obj = self.get_object()
        if not isinstance(request.data, Mapping):
            raise ValidationError("Operacja wymaga obiektu JSON.")
        if set(request.data) - {"version", "client", "policy"}:
            raise ValidationError("Nieznane pola operacji zapisu załącznika.")
        from pathlib import Path
        from documents.models import Document
        from .storage import storage_operation
        with storage_operation(source_message_id=obj.message_id) as writer:
            with transaction.atomic():
                message = Message.objects.select_for_update(of=("self",)).select_related("owner").get(pk=obj.message_id)
                require_owner(message, request.user)
                attachment = Attachment.objects.select_for_update().get(pk=pk)
                if attachment.document_id:
                    # A replay has no additional side effect, even if the caller still has its old version.
                    return Response({"document": DocumentSerializer(attachment.document).data, "message_version": message.version})
                check_version(message, request.data.get("version"))
                if attachment.blocked_reason or not attachment.file:
                    raise ValidationError("Ten załącznik nie spełnia reguł dokumentów.")
                if not request.data.get("client"):
                    raise ValidationError({"client": "Wybierz kartotekę dla dokumentu."})
                client, policy = linked_objects(request.data["client"], request.data.get("policy"))
                with attachment.file.open("rb") as source:
                    from django.core.files.base import ContentFile
                    upload = ContentFile(source.read(), name=attachment.original_name)
                serializer = DocumentSerializer(data={"client": client.pk, "policy": policy.pk if policy else None, "file": upload})
                serializer.is_valid(raise_exception=True)
                validated = dict(serializer.validated_data)
                payload = validated.pop("file")
                payload.seek(0)
                document = Document(author=request.user, **validated)
                document.file.name = writer.write(payload.read(), "originals", Path(document.original_name).suffix.lower())
                document.save()
                attachment.document = document
                attachment.save(update_fields=["document"])
                message.version += 1
                message.save(update_fields=["version"])
                record(request.user, "mail.document_created", "message", message.pk, client.pk, {
                    "attachment": attachment.pk, "part_key": attachment.part_key, "document": document.pk,
                    "client": client.pk, "policy": policy.pk if policy else None, "version": message.version,
                })
                record(request.user, "document.from_mail", "document", document.pk, client.pk, {
                    "message": message.pk, "attachment": attachment.pk,
                })
                transaction.on_commit(writer.release)
                return Response({"document": DocumentSerializer(document).data, "message_version": message.version}, status=201)


class MailboxViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = MailboxSerializer
    queryset = Mailbox.objects.all().order_by("id")

    def get_queryset(self):
        try:
            fingerprint = load_config(load_secret=False).fingerprint
            return self.queryset.annotate(current_first=Case(When(kind="imap", config_fingerprint=fingerprint, then=Value(0)), default=Value(1), output_field=IntegerField())).order_by("current_first", "-id")
        except MailConfigurationError:
            return self.queryset.order_by("-id")

    def list(self, request, *args, **kwargs):
        try:
            current_mailbox()
        except MailConfigurationError:
            # Broken server settings must not make the rest of the shared inbox unavailable.
            response = super().list(request, *args, **kwargs)
            response.data["configuration_error"] = "Błędna konfiguracja serwera poczty; administrator wdrożenia musi ją poprawić."
            return response
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def control(self, request, pk=None):
        if request.user.role != "ADMIN":
            raise PermissionDenied("Tylko administrator steruje integracją.")
        target = get_object_or_404(Mailbox, pk=pk)
        if not isinstance(request.data, Mapping):
            raise ValidationError("Operacja wymaga obiektu JSON.")
        if set(request.data) - {"version", "action"}:
            raise ValidationError("Adres i dane logowania konfiguruje wyłącznie administrator serwera.")
        from . import sync
        action_name = request.data.get("action")
        version = request.data.get("version")
        if type(version) is not int or version < 1:
            raise ValidationError({"version": "Podaj dodatnią wersję konfiguracji."})
        if action_name == "pause":
            mailbox = sync.control("pause", request.user, version, mailbox_id=target.pk)
            return Response(MailboxSerializer(mailbox).data)
        try:
            current = current_mailbox()
            if current.pk != target.pk:
                raise ValidationError("To źródło nie jest aktualną konfiguracją IMAP.")
            if current.version != version:
                raise Conflict("Stan integracji zmienił się. Odśwież go przed następną operacją.")
            if action_name == "test":
                return Response(sync.test_connection(actor=request.user))
            if action_name == "sync":
                return Response(sync.request_sync(actor=request.user))
            mailbox = sync.control("rebuild" if action_name == "recover" else action_name, request.user, version)
            return Response(MailboxSerializer(mailbox).data)
        except MailConfigurationError as error:
            raise ValidationError(str(error)) from None


@api_view(["GET"])
def mail_users(request):
    if request.user.role != "ADMIN":
        raise PermissionDenied("Lista do przekazania obsługi jest dostępna dla administratora.")
    query = request.query_params.get("search", "")[:200]
    if "\x00" in query:
        raise ValidationError({"search": "Zapytanie zawiera niedozwolony znak NUL."})
    users = User.objects.filter(is_active=True).filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)).order_by("username", "pk")
    pagination = PageNumberPagination()
    return pagination.get_paginated_response(EmployeeSerializer(pagination.paginate_queryset(users, request), many=True).data)
