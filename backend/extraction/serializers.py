from rest_framework import serializers

from .validation import draft_warnings, warning_digest
from .models import ApprovedRevision, EngineResult, ExtractionJob, ReviewDraft


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractionJob
        fields = ["id", "document", "status", "error", "created_at", "started_at", "finished_at"]


class EngineResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = EngineResult
        fields = ["id", "profile", "fields", "warnings", "pages"]


class DraftSerializer(serializers.ModelSerializer):
    warnings = serializers.SerializerMethodField()
    warning_digest = serializers.SerializerMethodField()

    def get_warnings(self, obj):
        return draft_warnings(obj.fields)

    def get_warning_digest(self, obj):
        return warning_digest(obj.fields)

    class Meta:
        model = ReviewDraft
        fields = ["id", "version", "fields", "updated_at", "approved_version", "profile", "origin", "warnings", "warning_digest"]


class RevisionSummarySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = ApprovedRevision
        fields = ["id", "number", "author_name", "created_at"]


class RevisionSerializer(RevisionSummarySerializer):
    class Meta(RevisionSummarySerializer.Meta):
        fields = RevisionSummarySerializer.Meta.fields + ["document", "fields", "profile", "warnings", "origin", "warning_confirmation"]


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class DraftPatchSerializer(VersionSerializer):
    fields = serializers.ListField(child=serializers.DictField(), max_length=1000)


class ApprovalSerializer(VersionSerializer):
    warning_digest = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    confirm_warnings = serializers.BooleanField(required=False, default=False)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class GroupAddSerializer(VersionSerializer):
    def validate(self, attrs):
        if set(self.initial_data) - {"version", "group"}:
            raise serializers.ValidationError("Schemat grupy jest określony przez serwer.")
        return attrs

    group = serializers.ChoiceField(choices=["participants", "coverage_items"])


class GroupRemoveSerializer(VersionSerializer):
    def validate(self, attrs):
        if set(self.initial_data) - {"version", "group_id"}:
            raise serializers.ValidationError("Usuń grupę przez jej tożsamość i wersję szkicu.")
        return attrs

    group_id = serializers.UUIDField()
