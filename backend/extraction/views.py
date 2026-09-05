import copy

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.audit import record
from documents.models import Document

from .models import ApprovedRevision, EngineResult, ExtractionJob, ReviewDraft
from .serializers import (
    DraftPatchSerializer,
    DraftSerializer,
    EngineResultSerializer,
    JobSerializer,
    RevisionSerializer,
    RevisionSummarySerializer,
    VersionSerializer,
)
from .services import VersionConflict, check_version, validate_fields
from .tasks import dispatch_job


class ExtractView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        with transaction.atomic():
            document = get_object_or_404(Document.objects.select_for_update(), pk=document_id)
            if document.mime_type not in {"application/pdf", "image/jpeg", "image/png"}:
                raise ValidationError({"detail": "Ten format jest załącznikiem bez automatycznego odczytu."})
            job = document.jobs.filter(status__in=["queued", "running"]).first()
            if job is None:
                job = ExtractionJob.objects.create(document=document, requested_by=request.user)
                record(request.user, "extraction_requested", "document", document.pk, client_id=document.client_id)
                transaction.on_commit(lambda: dispatch_job(job.pk))
        return Response(JobSerializer(job).data, status=202)


class ReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, document_id):
        document = get_object_or_404(Document, pk=document_id)
        job = document.jobs.first()
        result = EngineResult.objects.filter(job__document=document).order_by("-created_at", "-id").first()
        draft = ReviewDraft.objects.filter(document=document).first()
        return Response({
            "job": JobSerializer(job).data if job else None,
            "engine_result": EngineResultSerializer(result).data if result else None,
            "draft": DraftSerializer(draft).data if draft else None,
            "revisions": RevisionSummarySerializer(document.revisions.select_related("author"), many=True).data,
        })

    def patch(self, request, document_id):
        serializer = DraftPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(ReviewDraft.objects.select_for_update().select_related("document"), document_id=document_id)
            check_version(draft, serializer.validated_data["version"])
            fields, changed = validate_fields(draft.fields, serializer.validated_data["fields"], request.user)
            if changed:
                draft.fields = fields
                draft.version += 1
                draft.save()
                record(request.user, "review_saved", "document", document_id,
                       client_id=draft.document.client_id, metadata={"version": draft.version})
        return Response(DraftSerializer(draft).data)


class ReviewResetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(ReviewDraft.objects.select_for_update().select_related("document"), document_id=document_id)
            check_version(draft, serializer.validated_data["version"])
            latest = EngineResult.objects.filter(job__document_id=document_id).order_by("-created_at", "-id").first()
            if latest is None or not latest.profile:
                raise ValidationError({"detail": "Najnowszy wynik nie ma obsługiwanego profilu odczytu."})
            draft.fields = copy.deepcopy(latest.fields)
            draft.engine_result = latest
            draft.version += 1
            draft.save()
            record(request.user, "review_reset", "document", document_id,
                   client_id=draft.document.client_id, metadata={"version": draft.version})
        return Response(DraftSerializer(draft).data)


class ApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        serializer = VersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(
                ReviewDraft.objects.select_for_update().select_related("document", "engine_result"),
                document_id=document_id,
            )
            check_version(draft, serializer.validated_data["version"])
            if draft.approved_version == draft.version:
                raise VersionConflict("Ta wersja została już zatwierdzona. Kolejna rewizja wymaga korekty odczytu.")
            if not draft.engine_result.profile:
                raise ValidationError({"detail": "Brak profilu automatycznego odczytu."})
            previous = ApprovedRevision.objects.filter(document=draft.document).first()
            revision = ApprovedRevision.objects.create(
                document=draft.document, engine_result=draft.engine_result, number=previous.number + 1 if previous else 1,
                draft_version=draft.version, fields=copy.deepcopy(draft.fields), author=request.user,
                profile=draft.engine_result.profile, warnings=copy.deepcopy(draft.engine_result.warnings),
                document_name=draft.document.original_name, document_checksum=draft.document.checksum,
            )
            draft.approved_version = draft.version
            draft.save(update_fields=["approved_version"])
            record(request.user, "review_approved", "document", document_id,
                   client_id=draft.document.client_id, metadata={"revision_id": revision.pk, "number": revision.number})
        return Response(RevisionSerializer(revision).data, status=201)


class RevisionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, revision_id):
        revision = get_object_or_404(ApprovedRevision.objects.select_related("author"), pk=revision_id)
        return Response(RevisionSerializer(revision).data)
