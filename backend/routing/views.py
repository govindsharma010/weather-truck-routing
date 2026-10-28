import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import PlanRequestSerializer
from .services import geocoding, planner, routes, weather

logger = logging.getLogger(__name__)

UPSTREAM_ERRORS = (routes.RoutingError, weather.WeatherError, geocoding.GeocodingError)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def geocode(request):
    try:
        results = geocoding.search(request.query_params.get("q", ""), limit=5)
    except geocoding.GeocodingError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response({"results": results})


@api_view(["POST"])
def plan(request):
    serializer = PlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Invalid request.", "fields": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    d = serializer.validated_data

    req = planner.PlanRequest(
        origin=(d["origin"]["lat"], d["origin"]["lon"]),
        destination=(d["destination"]["lat"], d["destination"]["lon"]),
        departure=d["departure"],
        load_lb=d["load_lb"],
        interval_mi=d["checkpoint_interval_mi"],
        origin_label=d["origin"]["label"],
        destination_label=d["destination"]["label"],
    )
    try:
        return Response(planner.build_plan(req))
    except planner.PlanError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except UPSTREAM_ERRORS as exc:
        logger.warning("upstream failure: %s", exc)
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)