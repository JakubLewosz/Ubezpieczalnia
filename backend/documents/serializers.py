from rest_framework import serializers
from .models import Document
from .validation import inspect_upload


class DocumentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.display_name", read_only=True)
    author_name = serializers.CharField(source="author.username", read_only=True)
    file = serializers.FileField(write_only=True)
    duplicate_warnings = serializers.SerializerMethodField()
    latest_job = serializers.SerializerMethodField()
    review_status = serializers.SerializerMethodField()
    mail_source = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "mail_source",
            "client",
            "client_name",
            "policy",
            "file",
            "original_name",
            "mime_type",
            "size",
            "checksum",
            "category",
            "page_count",
            "created_at",
            "author_name",
            "duplicate_warnings",
            "latest_job",
            "review_status",
        ]
        read_only_fields = ["original_name", "mime_type", "size", "checksum", "page_count", "created_at"]

    def validate(self, attrs):
        if attrs["client"].archived:
            raise serializers.ValidationError({"client": "Przywróć kartotekę przed dodaniem dokumentu."})
        policy = attrs.get("policy")
        if policy and (policy.archived or not policy.participants.filter(client=attrs["client"]).exists()):
            raise serializers.ValidationError(
                {"policy": "Wybierz aktywną polisę z tą kartoteką jako uczestnikiem."}
            )
        attrs.update(inspect_upload(attrs["file"]))
        return attrs

    def create(self, validated_data):
        upload = validated_data.pop("file")
        document = Document(**validated_data)
        # Keep the instance and its private key available even if the DB INSERT fails.
        document.file.save(document.original_name, upload, save=False)
        try:
            document.save()
        except Exception:
            document.file.delete(save=False)
            raise
        return document

    def get_duplicate_warnings(self, obj):
        exists = Document.objects.exclude(pk=obj.pk).filter(checksum=obj.checksum).exists()
        return (
            ["Taki plik jest już w magazynie. Sprawdź przypisanie; kartoteki nie zostały scalone."]
            if exists
            else []
        )

    def get_latest_job(self, obj):
        from extraction.models import ExtractionJob
        from extraction.serializers import JobSerializer

        job = ExtractionJob.objects.filter(document=obj).order_by("-created_at", "-id").first()
        return JobSerializer(job).data if job else None

    def get_review_status(self, obj):
        if not obj.supports_extraction:
            return "attachment"
        from extraction.models import ReviewDraft, EngineResult

        draft = ReviewDraft.objects.filter(document=obj).first()
        if draft:
            return "approved" if draft.approved_version == draft.version else "draft"
        result = EngineResult.objects.filter(job__document=obj).order_by("-id").first()
        if result and not result.profile:
            return "unsupported"
        return "pending"

    def get_mail_source(self, obj):
        from correspondence.models import Attachment
        source = Attachment.objects.filter(document=obj).first()
        return {"message": source.message_id, "attachment": source.pk, "part_key": source.part_key} if source else None
