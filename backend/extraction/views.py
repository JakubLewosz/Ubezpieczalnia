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
    ApprovalSerializer,
    GroupAddSerializer,
    GroupRemoveSerializer,
    DraftPatchSerializer,
    DraftSerializer,
    EngineResultSerializer,
    JobSerializer,
    RevisionSerializer,
    RevisionSummarySerializer,
    VersionSerializer,
)
from .services import VersionConflict, add_group, check_version, reset_from_result, validate_fields
from .numbered import PROFILE as MANUAL_PROFILE, blank_profile
from .validation import draft_warnings, warning_digest
from exports.text import ExportValidationError, validate_xlsx_text
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
            reset_from_result(draft, latest)
            draft.engine_result = latest
            draft.profile = latest.profile
            draft.origin = "engine"
            draft.version += 1
            draft.save()
            record(request.user, "review_reset", "document", document_id,
                   client_id=draft.document.client_id, metadata={"version": draft.version})
        return Response(DraftSerializer(draft).data)


class ApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        serializer = ApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(
                ReviewDraft.objects.select_for_update(of=("self", "document")).select_related("document", "engine_result"),
                document_id=document_id,
            )
            check_version(draft, serializer.validated_data["version"])
            if draft.approved_version == draft.version:
                raise VersionConflict("Ta wersja została już zatwierdzona. Kolejna rewizja wymaga korekty odczytu.")
            validate_fields(draft.fields, draft.fields, request.user)
            warnings = draft_warnings(draft.fields)
            digest = warning_digest(draft.fields)
            if warnings and (not serializer.validated_data["confirm_warnings"] or serializer.validated_data["warning_digest"] != digest):
                raise ValidationError({"detail": "Potwierdź aktualne ostrzeżenia tej wersji szkicu.", "warnings": warnings, "warning_digest": digest})
            note = serializer.validated_data["note"].strip()
            if any(w["requires_note"] for w in warnings) and len(note) < 3:
                raise ValidationError({"note": "Przy istotnej sprzeczności opisz krótko decyzję (minimum 3 znaki)."})
            try:
                validate_xlsx_text(note, "Notatka zatwierdzenia")
                validate_xlsx_text(draft.document.original_name, "Nazwa dokumentu")
                for field in draft.fields:
                    for key in ["group", "code", "label", "value", "type", "unit"]:
                        validate_xlsx_text(field.get(key), f"{field['code']}.{key}")
            except ExportValidationError as exc:
                raise ValidationError({"detail": str(exc)}) from exc
            previous = ApprovedRevision.objects.filter(document=draft.document).first()
            revision = ApprovedRevision.objects.create(
                document=draft.document, engine_result=draft.engine_result, number=previous.number + 1 if previous else 1,
                draft_version=draft.version, fields=copy.deepcopy(draft.fields), author=request.user,
                profile=draft.profile, warnings=copy.deepcopy(warnings), origin=draft.origin,
                warning_confirmation={"version": draft.version, "warning_digest": digest, "confirmed": bool(warnings), "note": note},
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


class ReviewGroupsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        serializer = GroupAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(ReviewDraft.objects.select_for_update().select_related("document"), document_id=document_id)
            check_version(draft, serializer.validated_data["version"])
            group = serializer.validated_data["group"]
            group_id = add_group(draft, group, request.user)
            draft.version += 1
            draft.save()
            record(request.user, "review_group_added", "document", document_id, client_id=draft.document.client_id,
                   metadata={"group": group, "group_id": group_id, "version": draft.version})
        return Response(DraftSerializer(draft).data)

    def delete(self, request, document_id):
        serializer = GroupRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            draft = get_object_or_404(ReviewDraft.objects.select_for_update().select_related("document"), document_id=document_id)
            check_version(draft, serializer.validated_data["version"])
            group_id = str(serializer.validated_data["group_id"])
            fields = [f for f in draft.fields if f.get("group_id") == group_id]
            if not fields or fields[0]["group"] not in {"participants", "coverage_items"}:
                raise ValidationError({"group_id": "Można usuwać wyłącznie istniejącego uczestnika lub element zakresu."})
            group = fields[0]["group"]
            draft.group_counters[group] = max(draft.group_counters.get(group, 0), max(f["index"] + 1 for f in draft.fields if f["group"] == group))
            draft.fields = [f for f in draft.fields if f.get("group_id") != group_id]
            draft.version += 1
            draft.save()
            record(request.user, "review_group_removed", "document", document_id, client_id=draft.document.client_id,
                   metadata={"group": group, "group_id": group_id, "version": draft.version})
        return Response(DraftSerializer(draft).data)


class ReviewManualView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id):
        if request.data:
            raise ValidationError({"detail": "Ręczny profil ma schemat serwera; nie przesyłaj własnych pól."})
        with transaction.atomic():
            document = get_object_or_404(Document.objects.select_for_update(), pk=document_id)
            if ReviewDraft.objects.filter(document=document).exists():
                raise VersionConflict("Dokument ma już szkic. Wczytaj jego aktualną wersję.")
            job = document.jobs.first()
            if job is None or job.status not in {"succeeded", "failed"}:
                raise ValidationError({"detail": "Ręczne uzupełnienie jest dostępne po zakończonej próbie rozpoznania."})
            result = EngineResult.objects.filter(job=job).first()
            if result and result.profile:
                raise ValidationError({"detail": "Rozpoznano profil; użyj istniejącego odczytu."})
            if document.mime_type not in {"application/pdf", "image/png", "image/jpeg"}:
                raise ValidationError({"detail": "Ten format nie obsługuje podglądu ręcznego wniosku."})
            draft = ReviewDraft.objects.create(document=document, engine_result=result, profile=MANUAL_PROFILE,
                                               origin="manual", fields=blank_profile(manual=True, user=request.user))
            record(request.user, "review_manual_started", "document", document_id, client_id=document.client_id,
                   metadata={"profile": MANUAL_PROFILE, "job_id": job.pk, "version": draft.version})
        return Response(DraftSerializer(draft).data, status=201)
