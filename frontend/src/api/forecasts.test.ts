import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchForecastRuns, fetchPointForecast, intervalTileUrl, precipitationTileUrl } from './forecasts';

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
});
