from django.db import models
from django.contrib.auth.models import User


class Trip(models.Model):
    CYCLE_CHOICES = [
        ("70hrs/8days", "70 Hours/8 Days"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    current_location = models.CharField(max_length=255)
    pickup_location = models.CharField(max_length=255)
    dropoff_location = models.CharField(max_length=255)
    current_cycle_used = models.DecimalField(max_digits=5, decimal_places=2)
    cycle_type = models.CharField(
        max_length=20, choices=CYCLE_CHOICES, default="70hrs/8days"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Calculated fields
    total_distance = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    estimated_duration = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )

    # Map-related fields
    route_geometry = models.JSONField(null=True, blank=True)
    current_coords = models.JSONField(null=True, blank=True)  # [lon, lat]
    pickup_coords = models.JSONField(null=True, blank=True)   # [lon, lat]
    dropoff_coords = models.JSONField(null=True, blank=True)  # [lon, lat]

    def __str__(self):
        return f"Trip {self.id} ({self.current_location} → {self.dropoff_location})"


class TripLeg(models.Model):
    trip = models.ForeignKey(Trip, related_name="legs", on_delete=models.CASCADE)
    sequence = models.IntegerField()
    start_location = models.CharField(max_length=255)
    end_location = models.CharField(max_length=255)
    distance = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DecimalField(max_digits=5, decimal_places=2)  # hours
    rest_stop = models.BooleanField(default=False)
    fueling_stop = models.BooleanField(default=False)

    def __str__(self):
        return f"Leg {self.sequence} ({self.start_location} → {self.end_location})"


class DailyLog(models.Model):
    trip = models.ForeignKey(Trip, related_name="daily_logs", on_delete=models.CASCADE)
    day_number = models.IntegerField()
    date = models.DateField()
    total_hours = models.DecimalField(max_digits=4, decimal_places=2)
    driving_hours = models.DecimalField(max_digits=4, decimal_places=2)
    off_duty_hours = models.DecimalField(max_digits=4, decimal_places=2)
    sleeper_berth_hours = models.DecimalField(max_digits=4, decimal_places=2)

    def __str__(self):
        return f"Day {self.day_number} Log for Trip {self.trip.id}"
