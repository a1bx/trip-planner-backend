from rest_framework import serializers
from .models import Trip, TripLeg, DailyLog


class TripLegSerializer(serializers.ModelSerializer):
    # Ensure decimals are always floats for frontend
    distance = serializers.FloatField()
    duration = serializers.FloatField()

    class Meta:
        model = TripLeg
        fields = "__all__"


class DailyLogSerializer(serializers.ModelSerializer):
    # Cast decimals to float, format date
    total_hours = serializers.FloatField()
    driving_hours = serializers.FloatField()
    off_duty_hours = serializers.FloatField()
    sleeper_berth_hours = serializers.FloatField()
    date = serializers.DateField(format="%Y-%m-%d")

    class Meta:
        model = DailyLog
        fields = "__all__"


class TripSerializer(serializers.ModelSerializer):
    legs = TripLegSerializer(many=True, read_only=True)
    daily_logs = DailyLogSerializer(many=True, read_only=True)

    # Computed fields
    route_geometry = serializers.SerializerMethodField()
    markers = serializers.SerializerMethodField()

    # Cast decimals to floats here too
    total_distance = serializers.FloatField()
    estimated_duration = serializers.FloatField()
    current_cycle_used = serializers.FloatField()

    class Meta:
        model = Trip
        fields = "__all__"
        extra_fields = ["route_geometry", "markers"]

    def get_route_geometry(self, obj):
        """Return saved geometry or fallback from legs/coords."""
        if getattr(obj, "route_geometry", None):
            return obj.route_geometry

        coords = []

        # Build from trip legs
        if obj.legs.exists():
            for leg in obj.legs.all().order_by("sequence"):
                if getattr(leg, "start_coords", None):
                    coords.append(leg.start_coords)
                if getattr(leg, "end_coords", None):
                    coords.append(leg.end_coords)

        # Fallback from trip markers
        if not coords:
            if getattr(obj, "current_coords", None):
                coords.append(obj.current_coords)
            if getattr(obj, "pickup_coords", None):
                coords.append(obj.pickup_coords)
            if getattr(obj, "dropoff_coords", None):
                coords.append(obj.dropoff_coords)

        return {"type": "LineString", "coordinates": coords} if coords else None

    def get_markers(self, obj):
        """Return key markers for map plotting."""
        markers = {}
        if getattr(obj, "current_coords", None):
            markers["current"] = obj.current_coords
        if getattr(obj, "pickup_coords", None):
            markers["pickup"] = obj.pickup_coords
        if getattr(obj, "dropoff_coords", None):
            markers["dropoff"] = obj.dropoff_coords
        return markers or None
