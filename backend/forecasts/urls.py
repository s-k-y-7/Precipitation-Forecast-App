from django.urls import path

from forecasts.views import ForecastRunListView, PrecipitationTileView, IntervalTileView, PointForecastView, IndiaCoverageView

urlpatterns = [
    path("forecast-runs/", ForecastRunListView.as_view(), name="forecast-run-list"),
    path(
        "forecast-runs/<str:run_id>/precipitation/v1/<int:z>/<int:x>/<int:y>.png",
        PrecipitationTileView.as_view(),
        name="precipitation-tile",
    ),
    path("forecast-runs/<str:run_id>/precipitation/v2/<int:step>/<int:z>/<int:x>/<int:y>.png", IntervalTileView.as_view(), name="precipitation-interval-tile"),
    path("forecast-runs/<str:run_id>/precipitation/point/", PointForecastView.as_view(), name="precipitation-point"),
    path("coverage/india/", IndiaCoverageView.as_view(), name="india-coverage"),
]
