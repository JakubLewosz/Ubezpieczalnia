from django.db.models import Q
from rest_framework import serializers
from accounts.models import User
from clients.models import Client
from common.models import AuditEvent
from .models import Attachment, Mailbox, Message


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "is_active"]


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "part_key", "original_name", "mime_type", "size", "blocked_reason", "document"]


class MailboxSerializer(serializers.ModelSerializer):
    is_current = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    error_count = serializers.SerializerMethodField()

    class Meta:
        model = Mailbox
        fields = ["id", "kind", "is_current", "folder", "enabled", "state", "error_code", "error_message", "uidvalidity",
                  "boundary_uid", "discovered_uid", "pending_uidvalidity", "last_success", "last_attempt",
                  "version", "pending_count", "error_count"]

    def get_is_current(self, obj):
        from .config import MailConfigurationError, load_config
        try:
            return obj.kind == "imap" and obj.config_fingerprint == load_config(load_secret=False).fingerprint
        except MailConfigurationError:
            return False

    def get_pending_count(self, obj):
        return obj.messages.filter(fetch_state="pending").count()

    def get_error_count(self, obj):
        return obj.messages.filter(fetch_state="error").count()


class MessageSerializer(serializers.ModelSerializer):
    owner = EmployeeSerializer(read_only=True)
    completed_by = EmployeeSerializer(read_only=True)
    client_name = serializers.CharField(source="client.display_name", default=None)
    is_read = serializers.BooleanField(read_only=True, default=False)
    attachment_count = serializers.IntegerField(read_only=True, default=0)
    source_kind = serializers.CharField(source="mailbox.kind")

    class Meta:
        model = Message
        fields = ["id", "mailbox", "source_kind", "subject", "sender_name", "sender_address", "received_at", "declared_at",
                  "imported_at", "status", "owner", "claimed_at", "completed_by", "completed_at", "client", "client_name",
                  "policy", "version", "is_read", "attachment_count", "fetch_state", "fetch_error", "recovery_status"]


class MessageDetailSerializer(MessageSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    history = serializers.SerializerMethodField()
    client_candidates = serializers.SerializerMethodField()
    client_candidate_count = serializers.SerializerMethodField()
    related_messages = serializers.SerializerMethodField()

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["body_text", "note", "headers", "warnings", "attachments", "history",
                   "client_candidates", "client_candidate_count", "related_messages", "recovery_candidates", "raw_sha256"]

    def candidates(self, obj):
        return Client.objects.filter(email__iexact=obj.sender_address) if obj.sender_address else Client.objects.none()

    def get_client_candidates(self, obj):
        return list(self.candidates(obj).values("id", "display_name", "archived")[:20])

    def get_client_candidate_count(self, obj):
        return self.candidates(obj).count()

    def get_history(self, obj):
        # Work events are paginated separately if the history grows; detail provides latest 100.
        return [{"id": e.pk, "action": e.action, "actor_name": e.actor.username if e.actor else "Synchronizacja",
                 "created_at": e.created_at, "metadata": e.metadata}
                for e in AuditEvent.objects.filter(object_type="message", object_id=obj.pk).select_related("actor")[:100]]

    def get_related_messages(self, obj):
        ids = [obj.in_reply_to, *obj.references]
        ids = [v for v in ids if v]
        query = Q(message_id__in=ids)
        if obj.message_id:
            query |= Q(in_reply_to=obj.message_id)
        # Header matches provide context only; duplicates and identical subjects never merge work.
        return list(Message.objects.filter(query).exclude(pk=obj.pk).values("id", "subject", "status")[:20])
