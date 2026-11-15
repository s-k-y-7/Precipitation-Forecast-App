export type ForecastRun = {
  run_id: string;
  model: string;
  stream: string;
  resolution: string;
  parameter: string;
  initialization_time: string;
  valid_time: string;
  lead_hours: number;
  available_steps_hours: number[];
  source_provider: string;
  source_sha256: string;
  grid_metadata: Record<string, string | number>;
};

export type ForecastRunList = {
  latest_run_id: string | null;
  runs: ForecastRun[];
};

export async function fetchForecastRuns(signal?: AbortSignal): Promise<ForecastRunList> {
  const response = await fetch('/api/forecast-runs/', { signal });
  if (!response.ok) throw new Error(`Forecast runs could not be loaded (${response.status}).`);
  return response.json() as Promise<ForecastRunList>;
}

export function precipitationTileUrl(runId: string): string {
  return `/api/forecast-runs/${encodeURIComponent(runId)}/precipitation/v1/{z}/{x}/{y}.png`;
}

export type IndiaCoverage = GeoJSON.FeatureCollection | GeoJSON.Feature | GeoJSON.Geometry;
export type PointForecast = {
  run_id: string;
  requested_location: { lat: number; lon: number };
  grid_point: { lat: number; lon: number };
  intervals: { start_step_hours: number; end_step_hours: number; valid_time: string; precipitation_mm: number | null }[];
};

export type IntervalOverview = {
  run_id: string;
  start_step_hours: number;
  end_step_hours: number;
  max_precipitation_mm: number | null;
  max_grid_point: { lat: number; lon: number } | null;
  valid_grid_points: number;
};

export async function fetchIntervalOverview(runId: string, step: number, signal?: AbortSignal): Promise<IntervalOverview> {
  const response = await fetch(
    `/api/forecast-runs/${encodeURIComponent(runId)}/precipitation/summary/${step}/`,
    { signal },
  );
  if (!response.ok) throw new Error(`India-wide forecast overview could not be loaded (${response.status}).`);
  return response.json() as Promise<IntervalOverview>;
}

export type PlaceSearchResult = {
  id: number;
  name: string;
  admin1: string;
  latitude: number;
  longitude: number;
  population: number;
};

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<{ results: PlaceSearchResult[] }> {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`/api/places/search/?${params}`, { signal });
  if (!response.ok) throw new Error(`City search failed (${response.status}).`);
  return response.json() as Promise<{ results: PlaceSearchResult[] }>;
}

export async function fetchIndiaCoverage(signal?: AbortSignal): Promise<IndiaCoverage> {
  const response = await fetch('/api/coverage/india/', { signal });
  if (!response.ok) throw new Error('India forecast coverage could not be loaded.');
  return response.json() as Promise<IndiaCoverage>;
}

export async function fetchPointForecast(runId: string, lat: number, lon: number, signal?: AbortSignal): Promise<PointForecast> {
  const query = new URLSearchParams({ lat: String(lat), lon: String(lon) });
  const response = await fetch(`/api/forecast-runs/${encodeURIComponent(runId)}/precipitation/point/?${query}`, { signal });
  const result = await response.json() as PointForecast | { detail?: string };
  if (!response.ok) throw new Error('detail' in result ? result.detail || 'Point forecast failed.' : 'Point forecast failed.');
  return result as PointForecast;
}

export function intervalTileUrl(runId: string, step: number): string {
  return `/api/forecast-runs/${encodeURIComponent(runId)}/precipitation/v2/${step}/{z}/{x}/{y}.png`;
}
