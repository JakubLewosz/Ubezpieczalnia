from django.db import models
from django.utils import timezone
from common.normalization import normalize


class Policy(models.Model):
    insurer = models.CharField(max_length=200)
    number = models.CharField(max_length=100)
    insurance_type = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    premium = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="PLN")
    subject = models.TextField(blank=True, max_length=5000)
    archived = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    search_text = models.TextField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["end_date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")), name="policy_dates_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(premium__gte=0) | models.Q(premium__isnull=True),
                name="policy_premium_valid",
            ),
        ]

    @property
    def coverage_status(self):
        today = timezone.localdate()
        return "upcoming" if self.start_date > today else "expired" if self.end_date < today else "active"

    def save(self, *args, **kwargs):
        self.search_text = " ".join(
            normalize(v) for v in [self.insurer, self.number, self.insurance_type, self.subject]
        )
        super().save(*args, **kwargs)


class PolicyParticipant(models.Model):
    policy = models.ForeignKey(Policy, related_name="participants", on_delete=models.CASCADE)
    client = models.ForeignKey("clients.Client", related_name="policy_roles", on_delete=models.PROTECT)
    role = models.CharField(
        max_length=20, choices=[("policyholder", "Ubezpieczający"), ("insured", "Ubezpieczony")]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "client", "role"], name="unique_policy_participant_role"
            )
        ]
