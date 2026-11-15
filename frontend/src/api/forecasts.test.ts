import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchForecastRuns, precipitationTileUrl } from './forecasts';

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
});
