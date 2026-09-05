from rest_framework import serializers

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
    class Meta:
        model = ReviewDraft
        fields = ["id", "version", "fields", "updated_at", "approved_version"]


class RevisionSummarySerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = ApprovedRevision
        fields = ["id", "number", "author_name", "created_at"]


class RevisionSerializer(RevisionSummarySerializer):
    class Meta(RevisionSummarySerializer.Meta):
        fields = RevisionSummarySerializer.Meta.fields + ["document", "fields", "profile", "warnings"]


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class DraftPatchSerializer(VersionSerializer):
    fields = serializers.ListField(child=serializers.DictField(), max_length=1000)
