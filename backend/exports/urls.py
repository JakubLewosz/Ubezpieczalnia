from django.urls import path

from .views import RevisionExportView

urlpatterns = [path("revisions/<int:revision_id>/export/", RevisionExportView.as_view(), name="revision-export")]
