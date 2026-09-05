from rest_framework.decorators import api_view
from rest_framework.response import Response
from clients.models import Client
from documents.models import Document
from documents.serializers import DocumentSerializer
from policies.models import Policy
from policies.serializers import PolicySerializer
from policies.views import expiring


@api_view(["GET"])
def dashboard(request):
    from extraction.models import ExtractionJob
    from django.db.models import F, Q, OuterRef, Subquery

    latest = ExtractionJob.objects.filter(document=OuterRef("pk")).order_by("-created_at", "-id")
    documents = Document.objects.select_related("client", "author").annotate(
        job_status=Subquery(latest.values("status")[:1])
    )
    review = documents.filter(job_status="succeeded", draft__isnull=False).filter(
        Q(draft__approved_version__isnull=True) | ~Q(draft__approved_version=F("draft__version"))
    )
    from extraction.models import EngineResult

    review = review.filter(
        pk__in=EngineResult.objects.exclude(profile__isnull=True)
        .exclude(profile="")
        .values("job__document_id")
    )
    failed = documents.filter(job_status="failed")
    deadlines = expiring(Policy.objects.prefetch_related("participants__client"), 30)
    return Response(
        {
            "clients_count": Client.objects.filter(archived=False).count(),
            "review_count": review.count(),
            "failed_count": failed.count(),
            "expiring_count": deadlines.count(),
            "review_documents": DocumentSerializer(review[:8], many=True).data,
            "failed_documents": DocumentSerializer(failed[:8], many=True).data,
            "expiring_policies": PolicySerializer(deadlines[:8], many=True).data,
        }
    )
