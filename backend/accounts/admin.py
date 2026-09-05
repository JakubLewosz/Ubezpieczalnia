from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin
from .models import User


class OfficeAdminSite(AdminSite):
    site_header = "Broker Office — konta"
    site_title = "Administracja kontami"

    def login(self, request, extra_context=None):
        from django.shortcuts import redirect

        return redirect("/")

    def has_permission(self, request):
        return request.user.is_active and request.user.is_authenticated and request.user.role == "ADMIN"


class OfficeUserAdmin(UserAdmin):
    fieldsets = tuple(
        (title, options) for title, options in UserAdmin.fieldsets if title != "Permissions"
    ) + (("Rola kancelarii", {"fields": ("role", "is_active")}),)
    # No superuser or Django permission escalation through the office account form.
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Dane", {"fields": ("first_name", "last_name", "email")}),
        ("Dostęp", {"fields": ("role", "is_active")}),
        ("Daty", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Rola", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active")
    list_filter = ("role", "is_active")

    def has_module_permission(self, request):
        return request.user.role == "ADMIN"

    def has_view_permission(self, request, obj=None):
        return request.user.role == "ADMIN"

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission

    def has_delete_permission(self, request, obj=None):
        return False


office_admin = OfficeAdminSite(name="office_admin")
office_admin.register(User, OfficeUserAdmin)
