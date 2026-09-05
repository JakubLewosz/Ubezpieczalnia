"""An explicit offline source; it never connects to an IMAP host."""
from contextlib import nullcontext
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone
from correspondence.ingest import import_bytes
from correspondence.models import Mailbox, Message
from clients.models import Client

FIXTURES = ("application", "no-client", "candidates", "newsletter", "html-only", "malformed", "blocked", "oversized", "reply")


class Command(BaseCommand):
    help = "Jawnie dodaje syntetyczne .eml do osobnego źródła demo (bez sieci i OCR)."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", choices=FIXTURES)
        parser.add_argument("--all", action="store_true")
        parser.add_argument("--uid", type=int, help="Jawne UID do demonstracji idempotencji; tylko z --fixture.")

    def handle(self, *args, **options):
        if not settings.DEVELOPMENT:
            raise CommandError("Seed syntetycznej poczty wymaga DJANGO_ENV=development.")
        if bool(options["fixture"]) == bool(options["all"]):
            raise CommandError("Wybierz --fixture nazwa albo --all.")
        if options["uid"] is not None and (options["all"] or options["uid"] < 1):
            raise CommandError("--uid wymaga jednej fixture i dodatniej liczby.")
        for name in ([options["fixture"]] if options["fixture"] else FIXTURES):
            path = Path(settings.ROOT_DIR) / "fixtures/mail" / f"{name}.eml"
            raw = path.read_bytes()
            if b"X-Broker-Demo: DANE TESTOWE" not in raw:
                raise CommandError("Brak jawnego znacznika danych syntetycznych.")
            if name == "candidates":
                for first in ("Alicja", "Barbara"):
                    Client.objects.get_or_create(kind="person", first_name=first, last_name="Kandydatka Testowa", email="wspolny@example.invalid")
            with transaction.atomic():
                box, _ = Mailbox.objects.get_or_create(key="offline-demo", defaults={"kind": "demo", "state": "demo", "uidvalidity": 1, "boundary_uid": 0, "discovered_uid": 0})
                box = Mailbox.objects.select_for_update().get(pk=box.pk)
                uid = options["uid"] or (box.discovered_uid or 0) + 1
                mail, _ = Message.objects.get_or_create(mailbox=box, folder="INBOX", uidvalidity=1, uid=uid)
                box.discovered_uid = max(uid, box.discovered_uid or 0)
                box.save(update_fields=["discovered_uid"])
            context = override_settings(MAIL_MAX_ATTACHMENT_BYTES=1024) if name == "oversized" else nullcontext()
            with context:
                imported = import_bytes(mail.pk, raw, timezone.now())
            Mailbox.objects.filter(pk=box.pk).update(last_success=timezone.now())
            self.stdout.write(f"DANE TESTOWE: {name}, wiadomość {imported.pk}, stan {imported.fetch_state}, obsługa {imported.status}.")
