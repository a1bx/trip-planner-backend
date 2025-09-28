import requests
import os
from datetime import datetime, timedelta
import polyline


class RoutePlanner:
    def __init__(self):
        self.api_key = os.getenv("ORS_API_KEY")
        self.base_url = "https://api.openrouteservice.org"

        if not self.api_key:
            raise ValueError("Missing ORS_API_KEY in environment variables")

    def geocode(self, location: str):
        url = f"{self.base_url}/geocode/search"
        params = {"api_key": self.api_key, "text": location}

        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        if data.get("features"):
            return data["features"][0]["geometry"]["coordinates"]  # [lon, lat]
        raise ValueError(f"Could not geocode location: {location}")

    def calculate_route(self, start, end):
        url = f"{self.base_url}/v2/directions/driving-car"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {"coordinates": [start, end], "format": "geojson"}

        r = requests.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()

        if "features" in data:
            route = data["features"][0]
            distance = route["properties"]["summary"]["distance"] / 1609.34
            duration = route["properties"]["summary"]["duration"] / 3600
            geometry = route["geometry"]

        elif "routes" in data:
            route = data["routes"][0]
            distance = route["summary"]["distance"] / 1609.34
            duration = route["summary"]["duration"] / 3600

            geometry = None
            if isinstance(route.get("geometry"), dict):
                geometry = route["geometry"]
            elif isinstance(route.get("geometry"), str):
                decoded = polyline.decode(route["geometry"])
                geometry = {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in decoded],
                }
            if not geometry:
                raise ValueError("Route geometry missing or invalid")
        else:
            raise ValueError("Unexpected route response format")

        return {"distance": distance, "duration": duration, "geometry": geometry}

    def plan_trip_with_rest_stops(self, trip_data):
        current_coords = self.geocode(trip_data["current_location"])
        pickup_coords = self.geocode(trip_data["pickup_location"])
        dropoff_coords = self.geocode(trip_data["dropoff_location"])

        route_result = self.calculate_route(pickup_coords, dropoff_coords)

        distance = route_result["distance"]
        duration = route_result["duration"]
        geometry = route_result["geometry"]

        current_cycle_used = float(trip_data["current_cycle_used"])
        legs = self._calculate_eld_legs(duration, distance, current_cycle_used)
        daily_logs = self._generate_daily_logs(legs, current_cycle_used)

        return {
            "total_distance": round(distance, 2),
            "total_duration": round(duration, 2),
            "legs": legs,
            "daily_logs": daily_logs,
            "route_geometry": geometry,
            "markers": {
                "current": current_coords,
                "pickup": pickup_coords,
                "dropoff": dropoff_coords,
            },
        }

    # ---------------------- ELD Helpers ----------------------

    def _calculate_eld_legs(self, total_duration, total_distance, current_cycle_used):
        legs = []
        max_driving_segment = 11
        fueling_interval = 1000
        leg_sequence = 1
        accumulated_driving = 0
        segment_distance = 0
        current_location = "Start"

        while accumulated_driving < total_duration:
            segment_duration = min(
                max_driving_segment, total_duration - accumulated_driving
            )
            segment_distance_est = (segment_duration / total_duration) * total_distance

            if segment_distance + segment_distance_est >= fueling_interval:
                legs.append(
                    {
                        "sequence": leg_sequence,
                        "type": "fueling",
                        "duration": 0.5,
                        "distance": 0,
                        "start_location": current_location,
                        "end_location": current_location + " Fuel Stop",
                    }
                )
                leg_sequence += 1
                segment_distance = 0

            legs.append(
                {
                    "sequence": leg_sequence,
                    "type": "driving",
                    "duration": round(segment_duration, 2),
                    "distance": round(segment_distance_est, 2),
                    "start_location": current_location,
                    "end_location": f"Point {leg_sequence}",
                }
            )
            leg_sequence += 1
            accumulated_driving += segment_duration
            segment_distance += segment_distance_est
            current_location = f"Point {leg_sequence}"

            if accumulated_driving < total_duration and leg_sequence > 1:
                legs.append(
                    {
                        "sequence": leg_sequence,
                        "type": "rest",
                        "duration": 10,
                        "distance": 0,
                        "start_location": current_location,
                        "end_location": current_location + " Rest Stop",
                    }
                )
                leg_sequence += 1

        return legs

    def _generate_daily_logs(self, legs, current_cycle_used):
        daily_logs = []
        current_date = datetime.now().date()
        day_number = 1
        daily_activities = []
        current_day_hours = 0

        for leg in legs:
            if current_day_hours + leg["duration"] <= 24:
                daily_activities.append(leg)
                current_day_hours += leg["duration"]
            else:
                log = self._create_daily_log(daily_activities, day_number, current_date)
                daily_logs.append(log)
                day_number += 1
                current_date += timedelta(days=1)
                daily_activities = [leg]
                current_day_hours = leg["duration"]

        if daily_activities:
            log = self._create_daily_log(daily_activities, day_number, current_date)
            daily_logs.append(log)

        return daily_logs

    def _create_daily_log(self, activities, day_number, date):
        driving_hours = sum(
            leg["duration"] for leg in activities if leg["type"] == "driving"
        )
        rest_hours = sum(
            leg["duration"] for leg in activities if leg["type"] == "rest"
        )
        fueling_hours = sum(
            leg["duration"] for leg in activities if leg["type"] == "fueling"
        )

        total_hours = driving_hours + rest_hours + fueling_hours
        off_duty_hours = max(0, 14 - total_hours)

        return {
            "day_number": day_number,
            "date": date.isoformat(),
            "total_hours": round(total_hours, 2),
            "driving_hours": round(driving_hours, 2),
            "off_duty_hours": round(off_duty_hours, 2),
            "sleeper_berth_hours": round(rest_hours, 2),
        }
