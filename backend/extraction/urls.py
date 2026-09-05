from django.urls import path

from .views import ApproveView, ExtractView, ReviewResetView, ReviewView, RevisionView

urlpatterns = [
    path("documents/<int:document_id>/extract/", ExtractView.as_view(), name="document-extract"),
    path("documents/<int:document_id>/review/", ReviewView.as_view(), name="document-review"),
    path("documents/<int:document_id>/review/reset/", ReviewResetView.as_view(), name="document-review-reset"),
    path("documents/<int:document_id>/approve/", ApproveView.as_view(), name="document-approve"),
    path("revisions/<int:revision_id>/", RevisionView.as_view(), name="revision-detail"),
]
