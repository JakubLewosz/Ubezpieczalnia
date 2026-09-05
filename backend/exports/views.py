from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from .text import ExportValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.audit import record
from extraction.models import ApprovedRevision

from .profile import build_workbook


class RevisionExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, revision_id):
        revision = get_object_or_404(ApprovedRevision.objects.select_related("document"), pk=revision_id)
        try:
            content = build_workbook(revision)
        except (ExportValidationError, ValueError, TypeError, KeyError) as exc:
            detail = str(exc) if isinstance(exc, ExportValidationError) else "Historyczne dane nie mają obsługiwanego formatu eksportu."
            raise ValidationError({"detail": detail, "action": "Utwórz korektę i nową zatwierdzoną rewizję; historyczna rewizja pozostaje niezmienna."}) from exc
        record(request.user, "revision_exported", "document", revision.document_id,
               client_id=revision.document.client_id, metadata={"revision_id": revision.pk, "profile": "review_export_v0"})
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="review_export_v0_revision_{revision.pk}.xlsx"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
