from django.db import transaction
from rest_framework import serializers
from clients.models import Client
from .models import Policy, PolicyParticipant


class ParticipantSerializer(serializers.ModelSerializer):
    client = serializers.PrimaryKeyRelatedField(queryset=Client.objects.all())
    client_name = serializers.CharField(source="client.display_name", read_only=True)

    class Meta:
        model = PolicyParticipant
        fields = ["client", "role", "client_name"]


class PolicySerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True)
    document_ids = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    coverage_status = serializers.CharField(read_only=True)
    duplicate_warnings = serializers.SerializerMethodField()

    class Meta:
        model = Policy
        exclude = ["search_text"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "Koniec ochrony nie może poprzedzać początku."})
        if attrs.get("premium") is not None and attrs["premium"] < 0:
            raise serializers.ValidationError({"premium": "Składka nie może być ujemna."})
        currency = attrs.get("currency", getattr(self.instance, "currency", "PLN"))
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
            raise serializers.ValidationError({"currency": "Podaj trzyliterowy kod waluty."})
        attrs["currency"] = currency.upper()
        participants = attrs.get("participants")
        if participants is not None:
            pairs = [(p["client"].pk, p["role"]) for p in participants]
            if len(set(pairs)) != len(pairs):
                raise serializers.ValidationError({"participants": "Ta osoba ma już wskazaną rolę."})
            if not any(role == "policyholder" for _, role in pairs) or not any(
                role == "insured" for _, role in pairs
            ):
                raise serializers.ValidationError(
                    {"participants": "Dodaj ubezpieczającego i co najmniej jednego ubezpieczonego."}
                )
        client_ids = (
            {p["client"].pk for p in participants}
            if participants is not None
            else set(self.instance.participants.values_list("client_id", flat=True))
        )
        from documents.models import Document

        ids = attrs.get("document_ids")
        if ids is not None:
            docs = list(Document.objects.filter(pk__in=ids))
            if len(set(ids)) != len(ids) or len(docs) != len(ids):
                raise serializers.ValidationError({"document_ids": "Nieprawidłowa lista dokumentów."})
            if any(
                d.client_id not in client_ids
                or (d.policy_id and (not self.instance or d.policy_id != self.instance.pk))
                for d in docs
            ):
                raise serializers.ValidationError(
                    {
                        "document_ids": "Dokument musi należeć do uczestnika i nie może być przypisany do innej polisy."
                    }
                )
        elif self.instance and self.instance.documents.exclude(client_id__in=client_ids).exists():
            raise serializers.ValidationError(
                {"participants": "Odłącz dokumenty osoby przed usunięciem jej z uczestników."}
            )
        return attrs

    def _relations(self, instance, participants, ids):
        from documents.models import Document

        if participants is not None:
            instance.participants.all().delete()
            PolicyParticipant.objects.bulk_create(
                [PolicyParticipant(policy=instance, **p) for p in participants]
            )
        if ids is not None:
            # Serialize with uploads and other policy edits; a document has only one policy.
            list(Document.objects.select_for_update().filter(pk__in=ids))
            if (
                Document.objects.filter(pk__in=ids)
                .exclude(policy__isnull=True)
                .exclude(policy=instance)
                .exists()
            ):
                from common.api import Conflict

                raise Conflict("Dokument został przypisany do innej polisy.")
            instance.documents.exclude(pk__in=ids).update(policy=None)
            Document.objects.filter(pk__in=ids).update(policy=instance)

    @transaction.atomic
    def create(self, validated_data):
        participants = validated_data.pop("participants")
        ids = validated_data.pop("document_ids", [])
        obj = super().create(validated_data)
        self._relations(obj, participants, ids)
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        participants = validated_data.pop("participants", None)
        ids = validated_data.pop("document_ids", None)
        instance = super().update(instance, validated_data)
        self._relations(instance, participants, ids)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["document_ids"] = list(instance.documents.values_list("id", flat=True))
        return data

    def get_duplicate_warnings(self, obj):
        exists = (
            Policy.objects.exclude(pk=obj.pk)
            .filter(insurer__iexact=obj.insurer.strip(), number__iexact=obj.number.strip())
            .exists()
        )
        return (
            ["Możliwy duplikat numeru u tego samego ubezpieczyciela. Sprawdź okres i uczestników."]
            if exists
            else []
        )
