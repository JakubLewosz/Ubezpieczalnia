from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.audit import record
from extraction.models import ApprovedRevision

from .profile import build_workbook


class RevisionExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, revision_id):
        revision = get_object_or_404(ApprovedRevision.objects.select_related("document"), pk=revision_id)
        content = build_workbook(revision)
        record(request.user, "revision_exported", "document", revision.document_id,
               client_id=revision.document.client_id, metadata={"revision_id": revision.pk, "profile": "review_export_v0"})
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="review_export_v0_revision_{revision.pk}.xlsx"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
