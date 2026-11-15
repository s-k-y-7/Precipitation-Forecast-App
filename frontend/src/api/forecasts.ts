export type ForecastRun = {
  run_id: string;
  model: string;
  stream: string;
  resolution: string;
  parameter: string;
  initialization_time: string;
  valid_time: string;
  lead_hours: number;
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
