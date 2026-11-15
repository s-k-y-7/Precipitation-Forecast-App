import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from forecasts.models import ForecastRun
from forecasts.pipeline.grib import ForecastFieldError
from forecasts.pipeline.grid import GridMetadataError
from forecasts.pipeline.service import get_forecast_tile, get_interval_tile, get_point_forecast
from forecasts.pipeline.india import coverage_geometry
from forecasts.pipeline.places import search_places
from forecasts.serializers import ForecastRunSerializer


logger = logging.getLogger(__name__)


class PlaceSearchView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        query = request.query_params.get("q", "")
        response = Response({"results": search_places(query)})
        response["Cache-Control"] = "no-store"
        return response


class ForecastRunListView(APIView):
    def get(self, request):
        now = timezone.now()
        candidates = list(
            ForecastRun.objects.filter(
                Q(source_expires_at__gt=now) | Q(cache_expires_at__gt=now)
            ).order_by("-initialization_time")
        )
        runs = [run for run in candidates if run.available_steps_hours]
        serialized = ForecastRunSerializer(runs, many=True).data
        response = Response({"latest_run_id": runs[0].run_id if runs else None, "runs": serialized})
        response["Cache-Control"] = "no-store"
        return response


class PrecipitationTileView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, run_id: str, z: int, x: int, y: int):
        if not 0 <= z <= 10 or x < 0 or y < 0 or x >= 1 << z or y >= 1 << z:
            return Response({"detail": "Invalid tile coordinates."}, status=status.HTTP_400_BAD_REQUEST)
        run = ForecastRun.objects.filter(run_id=run_id).first()
        if run is None:
            return Response({"detail": "Forecast run is unavailable."}, status=status.HTTP_404_NOT_FOUND)
        now = timezone.now()
        if run.source_expires_at <= now and (run.cache_expires_at is None or run.cache_expires_at <= now):
            return Response({"detail": "Forecast run has expired."}, status=status.HTTP_410_GONE)
        try:
            tile, _created = get_forecast_tile(run, z, x, y)
        except (ForecastFieldError, GridMetadataError):
            return Response(
                {"detail": "The ECMWF field could not be validated or decoded."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception:
            # Do not expose upstream, filesystem, or configuration details in API responses.
            logger.exception("Forecast tile generation failed for run %s", run.run_id)
            return Response(
                {"detail": "Forecast tile generation failed. Try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            tile_file = tile.open("rb")
        except OSError:
            return Response(
                {"detail": "Forecast tile expired during retrieval. Try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        response = FileResponse(tile_file, content_type="image/png")
        remaining_ttl = max(
            0, settings.FORECAST_TILE_CACHE_TTL_SECONDS - int(timezone.now().timestamp() - tile.stat().st_mtime)
        )
        response["Cache-Control"] = f"public, max-age={remaining_ttl}"
        response["X-Forecast-Run"] = run.run_id
        response["X-Forecast-Valid-Time"] = run.valid_time.isoformat()
        response["X-Forecast-Lead-Hours"] = str(run.lead_hours)
        return response


class IntervalTileView(PrecipitationTileView):
    def get(self, request, run_id: str, step: int, z: int, x: int, y: int):
        if step not in settings.FORECAST_STEPS_HOURS:
            return Response({"detail": "Forecast step must be between +3h and +24h in 3-hour intervals."}, status=400)
        if not 0 <= z <= 10 or x < 0 or y < 0 or x >= 1 << z or y >= 1 << z:
            return Response({"detail": "Invalid tile coordinates."}, status=400)
        run = ForecastRun.objects.filter(run_id=run_id).first()
        if run is None or step not in run.available_steps_hours:
            return Response({"detail": "Forecast run or requested step is unavailable."}, status=404)
        now = timezone.now()
        if run.source_expires_at <= now and (run.cache_expires_at is None or run.cache_expires_at <= now):
            return Response({"detail": "Forecast run has expired."}, status=410)
        try:
            tile, _ = get_interval_tile(run, step, z, x, y)
        except (ForecastFieldError, GridMetadataError):
            return Response({"detail": "The ECMWF field could not be validated or decoded."}, status=502)
        except ValueError as error:
            return Response({"detail": str(error)}, status=422)
        except Exception:
            logger.exception("Forecast interval tile failed for %s step %s", run.run_id, step)
            return Response({"detail": "Forecast tile generation failed. Try again later."}, status=503)
        response = FileResponse(tile.open("rb"), content_type="image/png")
        remaining = max(0, settings.FORECAST_TILE_CACHE_TTL_SECONDS - int(timezone.now().timestamp() - tile.stat().st_mtime))
        response["Cache-Control"] = f"public, max-age={remaining}"
        response["X-Forecast-Run"] = run.run_id
        response["X-Forecast-Interval"] = f"{step - 3}/{step}"
        response["X-Forecast-Valid-Time"] = (run.initialization_time + timedelta(hours=step)).isoformat()
        return response


class PointForecastView(APIView):
    def get(self, request, run_id: str):
        try:
            lat, lon = float(request.query_params["lat"]), float(request.query_params["lon"])
        except (KeyError, ValueError, TypeError):
            return Response({"detail": "Provide valid lat and lon coordinates."}, status=400)
        try:
            data = get_point_forecast(run_id, lat, lon)
            return Response(data)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        except ForecastRun.DoesNotExist:
            return Response({"detail": "Forecast run is unavailable."}, status=404)
        except (ForecastFieldError, GridMetadataError):
            return Response({"detail": "The ECMWF field could not be validated or decoded."}, status=502)
        except Exception:
            logger.exception("Point forecast failed for run %s", run_id)
            return Response({"detail": "Forecast point query failed. Try again later."}, status=503)


class IndiaCoverageView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        response = Response(coverage_geometry())
        response["Cache-Control"] = "public, max-age=86400"
        return response
