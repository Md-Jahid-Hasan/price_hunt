from rest_framework import serializers


class PricePointSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    recorded_at = serializers.DateTimeField()