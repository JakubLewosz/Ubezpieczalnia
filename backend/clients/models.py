from django.db import models
from common.normalization import normalize


class Client(models.Model):
    kind = models.CharField(max_length=12, choices=[("person", "Osoba"), ("organization", "Organizacja")])
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    organization_name = models.CharField(max_length=200, blank=True)
    display_name = models.CharField(max_length=220, editable=False)
    pesel = models.CharField(max_length=11, blank=True)
    nip = models.CharField(max_length=20, blank=True)
    identity_key = models.CharField(max_length=40, blank=True, editable=False)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True, max_length=1000)
    note = models.TextField(blank=True, max_length=10000)
    archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    search_text = models.TextField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["identity_key"],
                condition=~models.Q(identity_key=""),
                name="unique_nonempty_client_identity",
            )
        ]

    def save(self, *args, **kwargs):
        self.display_name = (
            self.organization_name
            if self.kind == "organization"
            else f"{self.first_name} {self.last_name}".strip()
        )
        self.identity_key = (
            ("pesel:" + normalize(self.pesel))
            if self.kind == "person" and self.pesel
            else (("nip:" + normalize(self.nip)) if self.kind == "organization" and self.nip else "")
        )
        self.search_text = " ".join(
            normalize(v) for v in [self.display_name, self.pesel, self.nip, self.email, self.phone]
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_name
