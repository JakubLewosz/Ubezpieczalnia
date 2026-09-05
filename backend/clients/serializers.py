from django.db.models import Q
from rest_framework import serializers
from common.normalization import normalize
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    duplicate_warnings = serializers.SerializerMethodField()

    class Meta:
        model = Client
        exclude = ["identity_key", "search_text"]
        read_only_fields = ["display_name", "created_at", "updated_at"]

    def validate(self, attrs):
        def current(key, default=""):
            return attrs.get(key, getattr(self.instance, key, default))

        kind = current("kind")
        if kind == "person" and (not current("first_name").strip() or not current("last_name").strip()):
            raise serializers.ValidationError("Podaj imię i nazwisko osoby.")
        if kind == "organization" and not current("organization_name").strip():
            raise serializers.ValidationError({"organization_name": "Podaj nazwę organizacji."})
        for key, length in [("pesel", 11), ("nip", 10)]:
            value = current(key)
            if value and (
                not normalize(value).isascii()
                or not normalize(value).isdigit()
                or len(normalize(value)) != length
            ):
                raise serializers.ValidationError({key: f"Identyfikator powinien zawierać {length} cyfr."})
        if kind == "person" and current("nip"):
            raise serializers.ValidationError({"nip": "W tym profilu NIP zapisujemy przy organizacji."})
        if kind == "organization" and current("pesel"):
            raise serializers.ValidationError({"pesel": "PESEL dotyczy osoby fizycznej."})
        return attrs

    def get_duplicate_warnings(self, obj):
        condition = Q(display_name__iexact=obj.display_name)
        if obj.email:
            condition |= Q(email__iexact=obj.email)
        matches = Client.objects.exclude(pk=obj.pk).filter(condition)
        phone_matches = (
            Client.objects.exclude(pk=obj.pk).filter(search_text__contains=normalize(obj.phone))
            if obj.phone
            else Client.objects.none()
        )
        names = list((matches | phone_matches).distinct().values_list("display_name", flat=True)[:3])
        return (
            ["Możliwy duplikat: " + ", ".join(names) + ". Sprawdź kartoteki; nie zostały scalone."]
            if names
            else []
        )
