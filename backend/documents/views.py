from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from common.audit import record
from .models import Document
from .serializers import DocumentSerializer


def private_response(handle, content_type, filename=None, attachment=False):
    response = FileResponse(handle, content_type=content_type, as_attachment=attachment, filename=filename)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


class DocumentViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        qs = Document.objects.select_related("client", "author", "policy")
        client = self.request.query_params.get("client")
        if client:
            if not client.isdigit():
                raise ValidationError("Nieprawidłowa kartoteka.")
            qs = qs.filter(client_id=client)
        search = self.request.query_params.get("search", "").strip()
        return qs.filter(original_name__icontains=search) if search else qs

    def perform_create(self, serializer):
        obj = None
        try:
            with transaction.atomic():
                if serializer.validated_data.get("policy"):
                    from policies.models import Policy

                    policy = Policy.objects.select_for_update().get(pk=serializer.validated_data["policy"].pk)
                    if not policy.participants.filter(client=serializer.validated_data["client"]).exists():
                        raise ValidationError("Zmieniono uczestników polisy. Wybierz ponownie polisę.")
                obj = serializer.save(author=self.request.user)
                record(self.request.user, "document.uploaded", "document", obj.pk, obj.client_id)
        except Exception:
            if obj and obj.file:
                obj.file.delete(save=False)
            raise

    @action(detail=True, methods=["get"])
    def original(self, request, pk=None):
        obj = self.get_object()
        try:
            handle = obj.file.open("rb")
        except FileNotFoundError:
            raise Http404("Brak pliku w magazynie. Sprawdź odtworzenie kopii danych.")
        record(request.user, "document.downloaded", "document", obj.pk, obj.client_id)
        return private_response(handle, "application/octet-stream", obj.original_name, True)

    @action(detail=True, methods=["get"], url_path=r"pages/(?P<page>\d+)")
    def pages(self, request, pk=None, page=None):
        obj = self.get_object()
        if not obj.supports_extraction or not 1 <= int(page) <= obj.page_count:
            raise Http404("Brak takiej strony.")
        path = Path(settings.MEDIA_ROOT) / "previews" / str(obj.pk) / f"{int(page)}.png"
        if not path.is_file():
            raise Http404("Podgląd będzie dostępny po zakończeniu odczytu.")
        return private_response(path.open("rb"), "image/png")
