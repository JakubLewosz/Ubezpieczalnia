from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrator"
        EMPLOYEE = "EMPLOYEE", "Pracownik"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)

    def save(self, *args, **kwargs):
        self.is_staff = self.role == self.Role.ADMIN
        super().save(*args, **kwargs)


class LoginBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    since = models.DateTimeField()
