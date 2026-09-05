"""Short row-locked business transactions, separate from personal opening and IMAP state."""
from collections.abc import Mapping
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from accounts.models import User
from clients.models import Client
from policies.models import Policy
from common.api import Conflict
from common.audit import record
from .models import Message

ACTIVE = {"todo", "in_progress", "waiting"}
TERMINAL = {"done", "no_action"}


def check_version(message, version):
    if type(version) is not int or version < 1:
        raise ValidationError({"version": "Podaj dodatnią liczbę całkowitą wersji wiadomości."})
    if version != message.version:
        owner = message.owner.username if message.owner else "nieprzydzielona"
        raise Conflict(f"Wiadomość zmienił inny pracownik (wersja {message.version}, odpowiedzialny: {owner}). Wczytaj ją ponownie; zachowaj własną notatkę.")


def require_owner(message, actor):
    if not actor.is_active or (actor.role != "ADMIN" and message.owner_id != actor.pk):
        raise PermissionDenied("Obsługę, notatki i powiązania zmienia odpowiedzialny pracownik lub administrator.")


def linked_objects(client_id, policy_id):
    client = None
    policy = None
    if client_id is not None:
        if type(client_id) is not int or client_id < 1:
            raise ValidationError({"client": "Wybierz kartotekę."})
        client = Client.objects.select_for_update().filter(pk=client_id).first()
        if not client or client.archived:
            raise ValidationError({"client": "Wybierz aktywną kartotekę."})
    if policy_id is not None:
        if type(policy_id) is not int or policy_id < 1:
            raise ValidationError({"policy": "Wybierz polisę."})
        policy = Policy.objects.select_for_update().filter(pk=policy_id).first()
        if not client or not policy or policy.archived or not policy.participants.filter(client=client).exists():
            raise ValidationError({"policy": "Polisa musi być aktywna i obejmować wybranego klienta."})
    return client, policy


def event(message, actor, action, before):
    after = {name: getattr(message, name) for name in ("status", "owner_id", "client_id", "policy_id")}
    after["owner_name"] = message.owner.username if message.owner else None
    message.version += 1
    message.save()
    record(actor, f"mail.{action}", "message", message.pk, message.client_id, {
        "before": before, "after": after, "version": message.version,
        # Store the current note once, on Message; audit records fact/actor/time without duplicating content.
        "note_changed": action == "updated",
    })
    return message


@transaction.atomic
def change_work(message_id, actor, data, claim=False):
    if not isinstance(data, Mapping):
        raise ValidationError("Operacja wymaga obiektu JSON.")
    if not actor.is_active:
        raise PermissionDenied("Konto jest nieaktywne.")
    message = Message.objects.select_for_update(of=("self",)).select_related("owner").get(pk=message_id)
    check_version(message, data.get("version"))
    before = {name: getattr(message, name) for name in ("status", "owner_id", "client_id", "policy_id")}
    before["owner_name"] = message.owner.username if message.owner else None
    now = timezone.now()
    if claim:
        if set(data) - {"version"}:
            raise ValidationError("Przejęcie przyjmuje wyłącznie wersję.")
        if message.owner_id is not None or message.status != "todo":
            raise Conflict("Wiadomość została już przejęta albo zakończona. Wczytaj aktualnego właściciela.")
        message.owner = actor
        message.claimed_at = now
        message.status = "in_progress"
        return event(message, actor, "claimed", before)
    require_owner(message, actor)
    action = data.get("action", "update")
    allowed = {"version", "action"}
    if action == "update":
        allowed |= {"status", "note", "client", "policy"}
    elif action == "assign":
        allowed |= {"owner"}
    if set(data) - allowed:
        raise ValidationError("Operacja zawiera niedozwolone pola.")
    if action == "update":
        if "note" in data:
            note = data["note"]
            if not isinstance(note, str) or len(note) > 10000 or "\x00" in note:
                raise ValidationError({"note": "Notatka: tekst do 10000 znaków bez znaku NUL."})
            message.note = note
        if "client" in data or "policy" in data:
            message.client, message.policy = linked_objects(data.get("client", message.client_id), data.get("policy", message.policy_id))
        status = data.get("status", message.status)
        if status != message.status:
            if message.status in TERMINAL:
                raise ValidationError("Zakończoną pozycję otwórz jawną operacją ponownego otwarcia.")
            if not message.owner_id or not message.owner.is_active:
                raise ValidationError("Przejmij wiadomość lub przekaż ją aktywnemu pracownikowi przed zmianą stanu.")
            if status not in {"in_progress", "waiting", "done", "no_action"}:
                raise ValidationError({"status": "Niedozwolony stan; zwolnienie do todo ma osobną akcję."})
            if status in {"waiting", "no_action"} and len(message.note.strip()) < 3:
                raise ValidationError({"note": "Opisz krótko, na co czekamy lub dlaczego nie trzeba działania (minimum 3 znaki)."})
            message.status = status
            if status in TERMINAL:
                message.completed_at = now
                message.completed_by = actor
        elif status in {"waiting", "no_action"} and len(message.note.strip()) < 3:
            raise ValidationError({"note": "Nie można usunąć uzasadnienia tego stanu."})
        return event(message, actor, "updated", before)
    if action == "assign":
        if actor.role != "ADMIN":
            raise PermissionDenied("Tylko administrator przekazuje obsługę.")
        owner = data.get("owner")
        if type(owner) is not int or owner < 1:
            raise ValidationError({"owner": "Wybierz aktywnego pracownika."})
        employee = User.objects.select_for_update().filter(pk=owner, is_active=True).first()
        if not employee:
            raise ValidationError({"owner": "Pracownik nie istnieje lub jest nieaktywny."})
        if message.status in TERMINAL:
            raise ValidationError("Najpierw ponownie otwórz zakończoną pozycję.")
        message.owner = employee
        message.claimed_at = now
        if message.status == "todo":
            message.status = "in_progress"
        return event(message, actor, "assigned", before)
    if action == "release":
        if message.status in TERMINAL:
            raise ValidationError("Zakończoną wiadomość najpierw ponownie otwórz.")
        message.owner = None
        message.claimed_at = None
        message.status = "todo"
        return event(message, actor, "released", before)
    if action == "reopen":
        if message.status not in TERMINAL:
            raise ValidationError("Tylko zakończona wiadomość wymaga ponownego otwarcia.")
        if message.owner is None or not message.owner.is_active:
            message.owner = actor
            message.claimed_at = now
        message.status = "in_progress"
        message.completed_at = None
        message.completed_by = None
        return event(message, actor, "reopened", before)
    raise ValidationError({"action": "Nieznana operacja obsługi."})
