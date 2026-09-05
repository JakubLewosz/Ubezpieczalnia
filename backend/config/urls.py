from django.urls import include, path
from rest_framework.routers import DefaultRouter
from accounts.admin import office_admin
from accounts import views as auth
from clients.views import ClientViewSet
from documents.views import DocumentViewSet
from policies.views import PolicyViewSet
from common.views import dashboard
from correspondence.views import MessageViewSet, AttachmentViewSet, MailboxViewSet, mail_users

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("documents", DocumentViewSet, basename="document")
router.register("policies", PolicyViewSet, basename="policy")
router.register("messages", MessageViewSet, basename="message")
router.register("mail-attachments", AttachmentViewSet, basename="mail-attachment")
router.register("mailboxes", MailboxViewSet, basename="mailbox")
urlpatterns = [
    path("api/mail-users/", mail_users),
    path("admin/", office_admin.urls),
    path("api/auth/csrf/", auth.csrf),
    path("api/auth/login/", auth.sign_in),
    path("api/auth/logout/", auth.sign_out),
    path("api/auth/me/", auth.me),
    path("api/dashboard/", dashboard),
    path("api/", include("extraction.urls")),
    path("api/", include("exports.urls")),
    path("api/", include(router.urls)),
]
