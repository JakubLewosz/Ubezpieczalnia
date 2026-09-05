"""Explicit, repeatable seeding of visibly synthetic demonstration data."""

from datetime import timedelta
from decimal import Decimal
from getpass import getpass
from pathlib import Path
import sys

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from clients.models import Client
from common.audit import record
from documents.models import Document
from documents.validation import inspect_upload
from policies.models import Policy, PolicyParticipant


class Command(BaseCommand):
    help = "Jawnie utwórz konto developerskie i wyłącznie DANE TESTOWE. Bez domyślnego hasła."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin.demo")
        parser.add_argument("--role", choices=["ADMIN", "EMPLOYEE"], default="ADMIN")
        parser.add_argument("--password-stdin", action="store_true", help="Pobierz hasło z stdin, np. w CI.")
        parser.add_argument("--reset-password", action="store_true", help="Jawnie zmień hasło istniejącego konta.")
        parser.add_argument("--without-documents", action="store_true", help="Nie kopiuj dokumentów do magazynu.")

    def handle(self, *args, **options):
        if not settings.DEVELOPMENT:
            raise CommandError("Seed jest dostępny wyłącznie przy DJANGO_ENV=development.")
        user_model = get_user_model()
        existing = user_model.objects.filter(username=options["username"]).first()
        if existing and existing.role != options["role"]:
            raise CommandError("Konto ma inną rolę. Zmień ją świadomie w administracji kontami.")
        password = None
        if not existing or options["reset_password"]:
            candidate = existing or user_model(username=options["username"])
            password = sys.stdin.readline().rstrip("\r\n") if options["password_stdin"] else getpass("Nowe hasło (min. 12 znaków): ")
            if not options["password_stdin"] and password != getpass("Powtórz hasło: "):
                raise CommandError("Hasła różnią się.")
            try:
                validate_password(password, user=candidate)
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from None
        saved_files = []
        try:
            with transaction.atomic():
                user, _ = user_model.objects.get_or_create(username=options["username"], defaults={
                    "role": options["role"], "first_name": "DANE TESTOWE", "last_name": "Administrator" if options["role"] == "ADMIN" else "Pracownik",
                    "email": f"{'admin' if options['role'] == 'ADMIN' else 'pracownik'}@broker-demo.invalid",
                })
                if password:
                    user.set_password(password)
                    user.save()
                person, _ = Client.objects.get_or_create(email="alicja@broker-demo.invalid", defaults={
                    "kind": "person", "first_name": "Alicja", "last_name": "Demonstracyjna — DANE TESTOWE",
                    "address": "ul. Testowa 1, 00-000 Miasto Testowe", "note": "DANE TESTOWE. Kartoteka fikcyjna; PESEL celowo pusty.",
                })
                second, _ = Client.objects.get_or_create(email="bruno@broker-demo.invalid", defaults={
                    "kind": "person", "first_name": "Bruno", "last_name": "Przykładowy — DANE TESTOWE",
                    "address": "ul. Fikcyjna 2, 00-000 Miasto Testowe", "note": "DANE TESTOWE. Drugi ubezpieczony.",
                })
                organization, _ = Client.objects.get_or_create(email="biuro@firma-demo.invalid", defaults={
                    "kind": "organization", "organization_name": "Pracownia Przykładu — DANE TESTOWE",
                    "address": "Aleja Syntetyczna 3, 00-000 Miasto Testowe", "note": "DANE TESTOWE. Fikcyjna organizacja; NIP celowo pusty.",
                })
                today = timezone.localdate()
                for number, end_delta, premium, subject in [
                    ("TEST-POL-0001", 12, Decimal("1234.50"), "Pojazd demonstracyjny — DANE TESTOWE"),
                    ("TEST-POL-0002", 44, None, "Odpowiedzialność działalności — DANE TESTOWE"),
                ]:
                    policy, created = Policy.objects.get_or_create(
                        insurer="Towarzystwo Testowe — DANE TESTOWE", number=number,
                        defaults={"insurance_type": "Komunikacyjne" if premium else "OC działalności",
                                  "start_date": today - timedelta(days=300), "end_date": today + timedelta(days=end_delta),
                                  "premium": premium, "currency": "PLN", "subject": subject},
                    )
                    roles = [(person, "policyholder"), (person, "insured"), (second, "insured")] if premium else [(organization, "policyholder"), (organization, "insured")]
                    for client, role in roles:
                        PolicyParticipant.objects.get_or_create(policy=policy, client=client, role=role)
                    if created:
                        record(user, "demo_seed", "policy", policy.pk, client_id=roles[0][0].pk)
                if not options["without_documents"]:
                    fixture_dir = Path(settings.ROOT_DIR) / "fixtures/synthetic"
                    for filename in ["application_text.pdf", "application_scan.pdf", "application_mixed.pdf", "unsupported_property.pdf"]:
                        if Document.objects.filter(client=person, original_name=filename).exists():
                            continue
                        path = fixture_dir / filename
                        if not path.exists():
                            raise CommandError("Brak syntetycznych PDF. Uruchom scripts/generate_fixtures.py.")
                        upload = SimpleUploadedFile(filename, path.read_bytes())
                        info = inspect_upload(upload)
                        document = Document(client=person, author=user, category="DANE TESTOWE — wniosek", **info)
                        document.file.save(filename, upload, save=False)
                        saved_files.append((document.file.storage, document.file.name))
                        document.save()
                        record(user, "document_uploaded", "document", document.pk, client_id=person.pk)
                record(user, "demo_seed", "user", user.pk)
        except Exception:
            for storage, name in saved_files:
                storage.delete(name)
            raise
        self.stdout.write(self.style.SUCCESS(
            f"DANE TESTOWE gotowe. Konto: {user.username}; rola: {user.role}. Hasło nie zostało wypisane."
        ))
        self.stdout.write("Odczyt dokumentu uruchom świadomie w interfejsie. Seed nie tworzy wyników ekstrakcji.")
