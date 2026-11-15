import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type { PointForecast } from './api/forecasts';

const mapClick = vi.hoisted<{ current?: (event: { latlng: { lat: number; lng: number } }) => void }>(() => ({}));
const mapFlyTo = vi.hoisted(() => vi.fn());

vi.mock('react-leaflet', async () => {
  const { createElement } = await import('react');
  return {
    GeoJSON: () => null,
    MapContainer: ({ children }: { children: ReactNode }) => createElement('div', { 'data-testid': 'map' }, children),
    Marker: () => null,
    TileLayer: () => null,
    ZoomControl: () => null,
    useMap: () => ({ flyTo: mapFlyTo }),
    useMapEvents: (handlers: { click: (event: { latlng: { lat: number; lng: number } }) => void }) => {
      mapClick.current = handlers.click;
      return null;
    },
  };
});

import { App, complete24HourTotal } from './App';

const indiaGeometry = {
  type: 'FeatureCollection',
  features: [{
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [[[68, 6], [98, 6], [98, 37], [68, 37], [68, 6]]] },
  }],
} as GeoJSON.FeatureCollection;

describe('forecast app failure handling', () => {
  beforeEach(() => {
    mapClick.current = undefined;
    mapFlyTo.mockClear();
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).startsWith('/api/forecast-runs/')) {
        return Promise.resolve({ ok: false, status: 500 } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
    }));
  });

  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('does not discard a successfully loaded India boundary when the run API fails', async () => {
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Forecast runs could not be loaded (500).');
    expect(screen.getByRole('combobox', { name: 'Forecast run' })).toHaveTextContent('Forecast runs unavailable');

    await act(async () => {
      mapClick.current?.({ latlng: { lat: 23.26, lng: 77.41 } });
    });

    expect(screen.getByRole('alert')).not.toHaveTextContent('India only');
  });

  it('reports an empty validated run catalog as a missing run, not an India boundary error', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input) === '/api/forecast-runs/') {
        return Promise.resolve({ ok: true, json: async () => ({ latest_run_id: null, runs: [] }) } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
    }));
    render(<App />);
    await screen.findByText('No validated forecast runs are available.');

    await act(async () => {
      mapClick.current?.({ latlng: { lat: 23.26, lng: 77.41 } });
    });

    expect(screen.getByRole('alert')).toHaveTextContent('No validated forecast run is currently available.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('India only');
  });

  it('sends Leaflet latitude and longitude in the expected order and displays the point series', async () => {
    const run = {
      run_id: 'ifs-oper-test', model: 'ifs', stream: 'oper', resolution: '0p25', parameter: 'tp',
      initialization_time: '2026-11-14T12:00:00Z', valid_time: '2026-11-15T12:00:00Z', lead_hours: 24,
      available_steps_hours: [3, 6, 9, 12, 15, 18, 21, 24], source_provider: 'ecmwf-open-data',
      source_sha256: 'f'.repeat(64), grid_metadata: {},
    };
    const pointForecast = {
      run_id: run.run_id, requested_location: { lat: 23.26, lon: 77.41 }, grid_point: { lat: 23.25, lon: 77.5 },
      intervals: [3, 6, 9, 12, 15, 18, 21, 24].map((end_step_hours) => ({
        start_step_hours: end_step_hours - 3, end_step_hours,
        valid_time: '2026-11-14T15:00:00Z', precipitation_mm: end_step_hours === 3 ? 1.25 : 0,
      })),
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/forecast-runs/') {
        return Promise.resolve({ ok: true, json: async () => ({ latest_run_id: run.run_id, runs: [run] }) } as Response);
      }
      if (url === '/api/coverage/india/') return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
      if (url.includes('/precipitation/summary/')) return Promise.resolve({ ok: true, json: async () => ({
        run_id: run.run_id, start_step_hours: 0, end_step_hours: 3, max_precipitation_mm: 12.5,
        max_grid_point: { lat: 23.25, lon: 77.5 }, valid_grid_points: 1000,
      }) } as Response);
      return Promise.resolve({ ok: true, json: async () => pointForecast } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await screen.findByRole('button', { name: '+24h' });

    await act(async () => {
      mapClick.current?.({ latlng: { lat: 23.26, lng: 77.41 } });
    });

    expect(await screen.findByText('23.2600°, 77.4100°')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/forecast-runs/ifs-oper-test/precipitation/point/?lat=23.26&lon=77.41',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getAllByText('1.25 mm').length).toBeGreaterThan(0);
    expect(screen.getByText(/24-hour total/)).toHaveTextContent('1.25 mm');
    expect(screen.getByText('+0 to +3h precipitation · Valid 14 Nov 2026 · 8:30 PM IST')).toBeInTheDocument();
    const callsBeforeTimezoneChange = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'UTC' }));
    expect(screen.getByText('+0 to +3h precipitation · Valid 14 Nov 2026 · 3:00 PM UTC')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeTimezoneChange);
  });

  it('searches a city, flies the map to it, and loads its point forecast', async () => {
    const run = {
      run_id: 'ifs-oper-test', model: 'ifs', stream: 'oper', resolution: '0p25', parameter: 'tp',
      initialization_time: '2026-11-14T12:00:00Z', valid_time: '2026-11-15T12:00:00Z', lead_hours: 24,
      available_steps_hours: [3, 6, 9, 12, 15, 18, 21, 24], source_provider: 'ecmwf-open-data',
      source_sha256: 'f'.repeat(64), grid_metadata: {},
    };
    const forecast = {
      run_id: run.run_id, requested_location: { lat: 23.26, lon: 77.41 }, grid_point: { lat: 23.25, lon: 77.5 },
      intervals: [3, 6, 9, 12, 15, 18, 21, 24].map(end_step_hours => ({
        start_step_hours: end_step_hours - 3, end_step_hours, valid_time: '2026-11-14T15:00:00Z', precipitation_mm: 0,
      })),
    };
    const city = { id: 1, name: 'Bhopal', admin1: 'Madhya Pradesh', latitude: 23.26, longitude: 77.41, population: 100000 };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/forecast-runs/') return Promise.resolve({ ok: true, json: async () => ({ latest_run_id: run.run_id, runs: [run] }) } as Response);
      if (url === '/api/coverage/india/') return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
      if (url === '/api/places/search/?q=bhopal') return Promise.resolve({ ok: true, json: async () => ({ results: [city] }) } as Response);
      if (url.includes('/precipitation/summary/')) return Promise.resolve({ ok: true, json: async () => ({
        run_id: run.run_id, start_step_hours: 0, end_step_hours: 3, max_precipitation_mm: 12.5,
        max_grid_point: { lat: 23.25, lon: 77.5 }, valid_grid_points: 1000,
      }) } as Response);
      return Promise.resolve({ ok: true, json: async () => forecast } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    const input = screen.getByRole('combobox', { name: 'Search Indian city' });
    fireEvent.change(input, { target: { value: 'bhopal' } });
    fireEvent.click(await screen.findByRole('option', { name: /Bhopal/ }));

    expect(mapFlyTo).toHaveBeenCalledWith([23.26, 77.41], 8, { duration: 0.7 });
    expect(await screen.findByText('Bhopal')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/forecast-runs/ifs-oper-test/precipitation/point/?lat=23.26&lon=77.41',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('shows an India grid overview and updates it with the selected timeline interval', async () => {
    const run = {
      run_id: 'ifs-oper-test', model: 'ifs', stream: 'oper', resolution: '0p25', parameter: 'tp',
      initialization_time: '2026-11-14T12:00:00Z', valid_time: '2026-11-15T12:00:00Z', lead_hours: 24,
      available_steps_hours: [3, 6, 9, 12, 15, 18, 21, 24], source_provider: 'ecmwf-open-data',
      source_sha256: 'f'.repeat(64), grid_metadata: {},
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/forecast-runs/') return Promise.resolve({ ok: true, json: async () => ({ latest_run_id: run.run_id, runs: [run] }) } as Response);
      if (url === '/api/coverage/india/') return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
      if (url.includes('/precipitation/summary/')) {
        const endStep = Number(url.match(/summary\/(\d+)\/$/)?.[1]);
        return Promise.resolve({ ok: true, json: async () => ({
          run_id: run.run_id, start_step_hours: endStep - 3, end_step_hours: endStep,
          max_precipitation_mm: endStep === 3 ? 5 : 10,
          max_grid_point: { lat: 23.25, lon: 77.5 }, valid_grid_points: 1000,
        }) } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    expect(await screen.findByText('5.00 mm')).toBeInTheDocument();
    expect(await screen.findByText('14 Nov 2026 · 8:30 PM IST')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '+6h' }));

    expect(await screen.findByText('10.00 mm')).toBeInTheDocument();
    expect(await screen.findByText('14 Nov 2026 · 11:30 PM IST')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/forecast-runs/ifs-oper-test/precipitation/summary/6/',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('polls for new runs every five minutes while preserving an available selection', async () => {
    const oldRun = {
      run_id: 'ifs-oper-old', model: 'ifs', stream: 'oper', resolution: '0p25', parameter: 'tp',
      initialization_time: '2026-11-14T00:00:00Z', valid_time: '2026-11-15T00:00:00Z', lead_hours: 24,
      available_steps_hours: [3, 6, 9, 12, 15, 18, 21, 24], source_provider: 'ecmwf-open-data',
      source_sha256: 'a'.repeat(64), grid_metadata: {},
    };
    const newRun = {
      ...oldRun, run_id: 'ifs-oper-new', initialization_time: '2026-11-14T12:00:00Z',
      valid_time: '2026-11-15T12:00:00Z', source_sha256: 'b'.repeat(64),
    };
    let catalogRequests = 0;
    let refreshCatalog: (() => void) | undefined;
    vi.spyOn(window, 'setInterval').mockImplementation((handler, delay) => {
      if (delay === 5 * 60 * 1000 && typeof handler === 'function') refreshCatalog = handler as () => void;
      return 1;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/forecast-runs/') {
        catalogRequests += 1;
        const catalog = catalogRequests === 1
          ? { latest_run_id: oldRun.run_id, runs: [oldRun] }
          : { latest_run_id: newRun.run_id, runs: [newRun, oldRun] };
        return Promise.resolve({ ok: true, json: async () => catalog } as Response);
      }
      if (url === '/api/coverage/india/') return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
      if (url.includes('/precipitation/summary/')) return Promise.resolve({ ok: true, json: async () => ({
        run_id: oldRun.run_id, start_step_hours: 0, end_step_hours: 3, max_precipitation_mm: 0,
        max_grid_point: null, valid_grid_points: 1000,
      }) } as Response);
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await screen.findByRole('option', { name: 'Latest forecast run' });

    expect(catalogRequests).toBe(1);
    expect(refreshCatalog).toBeDefined();
    await act(async () => {
      refreshCatalog?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(catalogRequests).toBe(2);
    expect(screen.getByRole('combobox', { name: 'Forecast run' })).toHaveValue(oldRun.run_id);
    expect(screen.getByRole('option', { name: /14 Nov 2026, 5:30 AM IST/ })).toBeInTheDocument();
  });

  it('defaults to IST and changes displayed timezones without reloading forecast data', async () => {
    const run = {
      run_id: 'ifs-oper-time-test', model: 'ifs', stream: 'oper', resolution: '0p25', parameter: 'tp',
      initialization_time: '2026-11-14T18:30:00Z', valid_time: '2026-11-15T18:30:00Z', lead_hours: 24,
      available_steps_hours: [3, 6, 9, 12, 15, 18, 21, 24], source_provider: 'ecmwf-open-data',
      source_sha256: 'f'.repeat(64), grid_metadata: {},
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/forecast-runs/') return Promise.resolve({ ok: true, json: async () => ({ latest_run_id: run.run_id, runs: [run] }) } as Response);
      if (url === '/api/coverage/india/') return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
      if (url.includes('/precipitation/summary/')) return Promise.resolve({ ok: true, json: async () => ({
        run_id: run.run_id, start_step_hours: 0, end_step_hours: 3, max_precipitation_mm: 0,
        max_grid_point: { lat: 23.25, lon: 77.5 }, valid_grid_points: 1000,
      }) } as Response);
      return Promise.resolve({ ok: true, json: async () => ({}) } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);

    expect(await screen.findByText('15 Nov 2026 · 3:00 AM IST')).toBeInTheDocument();
    const callsBeforeTimezoneChange = fetchMock.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'UTC' }));

    expect(await screen.findByText('14 Nov 2026 · 9:30 PM UTC')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeTimezoneChange);
  });

  it('shows a 24-hour point total only when every step is valid and ordered', () => {
    const point: PointForecast = {
      run_id: 'ifs-test', requested_location: { lat: 23, lon: 77 }, grid_point: { lat: 23, lon: 77 },
      intervals: [3, 6, 9, 12, 15, 18, 21, 24].map((end_step_hours, index) => ({
        start_step_hours: end_step_hours - 3, end_step_hours, valid_time: '', precipitation_mm: index + 1,
      })),
    };
    expect(complete24HourTotal(point)).toBe(36);
    point.intervals[3].precipitation_mm = null;
    expect(complete24HourTotal(point)).toBeNull();
  });
});
