from django.conf import settings
from rest_framework import serializers

from .services import geocoding


class PlaceField(serializers.Field):
    """A place is either ``{"lat", "lon", "label"?}`` or free text we geocode to the top match."""

    default_error_messages = {"invalid": "Provide a place as {lat, lon} or a search string.", "not_found": "Could not find that place: {text}"}

    def to_internal_value(self, data):
        if isinstance(data, dict):
            try:
                lat, lon = float(data["lat"]), float(data["lon"])
            except (KeyError, TypeError, ValueError):
                self.fail("invalid")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise serializers.ValidationError("Latitude/longitude out of range.")
            return {"lat": lat, "lon": lon, "label": str(data.get("label") or f"{lat:.4f}, {lon:.4f}")}
        if isinstance(data, str) and data.strip():
            hits = geocoding.search(data, limit=1)
            if not hits:
                self.fail("not_found", text=data)
            return hits[0]
        self.fail("invalid")

    def to_representation(self, value):
        return value


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceField()
    destination = PlaceField()
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=1, max_value=settings.MAX_LOAD_LB)
    checkpoint_interval_mi = serializers.ChoiceField(
        choices=list(settings.ALLOWED_CHECKPOINT_INTERVALS), default=settings.DEFAULT_CHECKPOINT_INTERVAL
    )