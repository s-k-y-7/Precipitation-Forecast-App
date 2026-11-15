import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchForecastRuns, fetchIntervalOverview, fetchPointForecast, intervalTileUrl, precipitationTileUrl, searchPlaces } from './forecasts';

afterEach(() => vi.restoreAllMocks());

describe('forecast API helpers', () => {
  it('loads the real run catalog from the backend', async () => {
    const payload = { latest_run_id: 'ifs-oper-test', runs: [] };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));

    await expect(fetchForecastRuns()).resolves.toEqual(payload);
    expect(fetch).toHaveBeenCalledWith('/api/forecast-runs/', { signal: undefined });
  });

  it('reports failed catalog requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    await expect(fetchForecastRuns()).rejects.toThrow('Forecast runs could not be loaded (503).');
  });

  it('creates run-scoped XYZ tile urls', () => {
    expect(precipitationTileUrl('ifs-oper-20261114T00Z-t24')).toBe(
      '/api/forecast-runs/ifs-oper-20261114T00Z-t24/precipitation/v1/{z}/{x}/{y}.png',
    );
  });

  it('creates a time-step scoped interval tile url', () => {
    expect(intervalTileUrl('ifs-oper-test', 12)).toBe(
      '/api/forecast-runs/ifs-oper-test/precipitation/v2/12/{z}/{x}/{y}.png',
    );
  });

  it('requests a real location series and surfaces India-only errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'This forecast currently covers India only.' }),
    }));

    await expect(fetchPointForecast('ifs-test', 23.8, 90.4)).rejects.toThrow('This forecast currently covers India only.');
    expect(fetch).toHaveBeenCalledWith('/api/forecast-runs/ifs-test/precipitation/point/?lat=23.8&lon=90.4', { signal: undefined });
  });

  it('queries the India-only place search endpoint with encoded input and cancellation', async () => {
    const result = { results: [{ id: 1, name: 'New Delhi', admin1: 'Delhi', latitude: 28.6, longitude: 77.2, population: 1000 }] };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => result }));
    const signal = new AbortController().signal;

    await expect(searchPlaces('New Delhi & NCR', signal)).resolves.toEqual(result);
    expect(fetch).toHaveBeenCalledWith('/api/places/search/?q=New+Delhi+%26+NCR', { signal });
  });

  it('loads an interval overview scoped to the selected run and time step', async () => {
    const result = { run_id: 'ifs-test', start_step_hours: 3, end_step_hours: 6, max_precipitation_mm: 12.5,
      max_grid_point: { lat: 23.25, lon: 77.5 }, valid_grid_points: 1000 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => result }));
    const signal = new AbortController().signal;

    await expect(fetchIntervalOverview('ifs-test', 6, signal)).resolves.toEqual(result);
    expect(fetch).toHaveBeenCalledWith('/api/forecast-runs/ifs-test/precipitation/summary/6/', { signal });
  });
});
