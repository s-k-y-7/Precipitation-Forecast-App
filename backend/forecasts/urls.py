from django.urls import path

from forecasts.views import ForecastRunListView, PrecipitationTileView

urlpatterns = [
    path("forecast-runs/", ForecastRunListView.as_view(), name="forecast-run-list"),
    path(
        "forecast-runs/<str:run_id>/precipitation/v1/<int:z>/<int:x>/<int:y>.png",
        PrecipitationTileView.as_view(),
        name="precipitation-tile",
    ),
]
