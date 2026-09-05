import hashlib
import json
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.audit import record
from .models import LoginBucket


def user_data(user):
    return {key: getattr(user, key) for key in ("id", "username", "first_name", "last_name", "role")}


@require_GET
@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
@csrf_protect
def sign_in(request):
    try:
        data = json.loads(request.body)
        username, password = data.get("username", ""), data.get("password", "")
        if (
            not isinstance(username, str)
            or not isinstance(password, str)
            or len(username) > 150
            or len(password) > 1024
        ):
            raise ValueError
    except (ValueError, AttributeError):
        return JsonResponse({"detail": "Nieprawidłowe dane logowania."}, status=400)
    # IP is taken from the socket, never an untrusted forwarding header.
    ip = request.META.get("REMOTE_ADDR", "")
    keys = sorted(
        [hashlib.sha256(v.encode()).hexdigest() for v in (f"ip:{ip}", f"user:{username.casefold()}")]
    )
    now = timezone.now()
    with transaction.atomic():
        buckets = []
        for key in keys:
            bucket, _ = LoginBucket.objects.get_or_create(key=key, defaults={"since": now})
            bucket = LoginBucket.objects.select_for_update().get(pk=bucket.pk)
            if bucket.since + timedelta(seconds=settings.LOGIN_WINDOW_SECONDS) <= now:
                bucket.failures, bucket.since = 0, now
            buckets.append(bucket)
        if any(b.failures >= settings.LOGIN_MAX_ATTEMPTS for b in buckets):
            response = JsonResponse({"detail": "Zbyt wiele prób. Spróbuj ponownie za 15 minut."}, status=429)
            response["Retry-After"] = str(settings.LOGIN_WINDOW_SECONDS)
            return response
        user = authenticate(request, username=username, password=password)
        for bucket in buckets:
            bucket.failures = 0 if user else bucket.failures + 1
            bucket.save()
    if not user:
        return JsonResponse({"detail": "Nieprawidłowy login lub hasło."}, status=400)
    login(request, user)
    record(user, "login", "user", user.pk)
    return JsonResponse(user_data(user))


@api_view(["GET"])
def me(request):
    return Response(user_data(request.user))


@api_view(["POST"])
def sign_out(request):
    record(request.user, "logout", "user", request.user.pk)
    logout(request)
    return Response({"detail": "Wylogowano."})
