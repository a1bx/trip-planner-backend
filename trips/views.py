from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import Trip, TripLeg, DailyLog
from .serializers import TripSerializer
from .services import RoutePlanner
import traceback
from datetime import datetime
from decimal import Decimal


@method_decorator(csrf_exempt, name='dispatch')
class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=["post"])
    def plan_trip(self, request):
        try:
            planner = RoutePlanner()
            trip_data = request.data

            # Validate input
            required_fields = [
                "current_location",
                "pickup_location",
                "dropoff_location",
                "current_cycle_used",
            ]
            missing_fields = [f for f in required_fields if f not in trip_data]
            if missing_fields:
                return Response(
                    {"error": "Missing required fields", "missing_fields": missing_fields},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Plan trip
            trip_plan = planner.plan_trip_with_rest_stops(trip_data)
            if not trip_plan:
                return Response(
                    {"error": "Failed to calculate route"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get or create default user
            default_user, _ = User.objects.get_or_create(
                username="default_user",
                defaults={
                    "email": "default@example.com",
                    "password": "defaultpassword123",
                },
            )

            # Save Trip
            trip = Trip.objects.create(
                user=default_user,
                current_location=trip_data["current_location"],
                pickup_location=trip_data["pickup_location"],
                dropoff_location=trip_data["dropoff_location"],
                current_cycle_used=Decimal(str(trip_data["current_cycle_used"])),
                total_distance=Decimal(str(trip_plan["total_distance"])),
                estimated_duration=Decimal(str(trip_plan["total_duration"])),
                route_geometry=trip_plan.get("route_geometry"),
                current_coords=trip_plan["markers"].get("current"),
                pickup_coords=trip_plan["markers"].get("pickup"),
                dropoff_coords=trip_plan["markers"].get("dropoff"),
            )

            # Save Legs
            for leg_data in trip_plan.get("legs", []):
                TripLeg.objects.create(
                    trip=trip,
                    sequence=leg_data["sequence"],
                    start_location=leg_data.get("start_location", ""),
                    end_location=leg_data.get("end_location", ""),
                    distance=Decimal(str(leg_data["distance"])),
                    duration=Decimal(str(leg_data["duration"])),
                    rest_stop=(leg_data.get("type") == "rest"),
                    fueling_stop=(leg_data.get("type") == "fueling"),
                )

            # Save Logs
            for log_data in trip_plan.get("daily_logs", []):
                log_date = log_data["date"]
                if isinstance(log_date, str):
                    log_date = datetime.strptime(log_date, "%Y-%m-%d").date()

                DailyLog.objects.create(
                    trip=trip,
                    day_number=log_data["day_number"],
                    date=log_date,
                    total_hours=Decimal(str(log_data["total_hours"])),
                    driving_hours=Decimal(str(log_data["driving_hours"])),
                    off_duty_hours=Decimal(str(log_data["off_duty_hours"])),
                    sleeper_berth_hours=Decimal(str(log_data["sleeper_berth_hours"])),
                )

            # Serialize Response
            serializer = self.get_serializer(trip)
            return Response(serializer.data)

        except Exception as e:
            traceback.print_exc()
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )