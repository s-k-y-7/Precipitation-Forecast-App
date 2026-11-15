import logging

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
from forecasts.pipeline.service import get_forecast_tile
from forecasts.serializers import ForecastRunSerializer


logger = logging.getLogger(__name__)


class ForecastRunListView(APIView):
    def get(self, request):
        now = timezone.now()
        runs = list(
            ForecastRun.objects.filter(
                Q(source_expires_at__gt=now) | Q(cache_expires_at__gt=now)
            ).order_by("-initialization_time")
        )
        serialized = ForecastRunSerializer(runs, many=True).data
        response = Response({"latest_run_id": runs[0].run_id if runs else None, "runs": serialized})
        response["Cache-Control"] = "no-store"
        return response


class PrecipitationTileView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, run_id: str, z: int, x: int, y: int):
        if z > 10 or x >= 1 << z or y >= 1 << z:
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
            0, settings.FORECAST_CACHE_TTL_SECONDS - int(timezone.now().timestamp() - tile.stat().st_mtime)
        )
        response["Cache-Control"] = f"public, max-age={remaining_ttl}"
        response["X-Forecast-Run"] = run.run_id
        response["X-Forecast-Valid-Time"] = run.valid_time.isoformat()
        response["X-Forecast-Lead-Hours"] = str(run.lead_hours)
        return response
