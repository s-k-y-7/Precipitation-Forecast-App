import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

const mapClick = vi.hoisted<{ current?: (event: { latlng: { lat: number; lng: number } }) => void }>(() => ({}));

vi.mock('react-leaflet', async () => {
  const { createElement } = await import('react');
  return {
    GeoJSON: () => null,
    MapContainer: ({ children }: { children: ReactNode }) => createElement('div', { 'data-testid': 'map' }, children),
    Marker: () => null,
    TileLayer: () => null,
    ZoomControl: () => null,
    useMapEvents: (handlers: { click: (event: { latlng: { lat: number; lng: number } }) => void }) => {
      mapClick.current = handlers.click;
      return null;
    },
  };
});

import { App } from './App';

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
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input).startsWith('/api/forecast-runs/')) {
        return Promise.resolve({ ok: false, status: 500 } as Response);
      }
      return Promise.resolve({ ok: true, json: async () => indiaGeometry } as Response);
    }));
  });

  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('does not discard a successfully loaded India boundary when the run API fails', async () => {
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Forecast runs could not be loaded (500).');
    expect(screen.getByRole('option')).toHaveTextContent('Forecast runs unavailable');

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
      return Promise.resolve({ ok: true, json: async () => pointForecast } as Response);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<App />);
    await screen.findByRole('button', { name: '+24h' });

    await act(async () => {
      mapClick.current?.({ latlng: { lat: 23.26, lng: 77.41 } });
    });

    expect(await screen.findByText('Selected 23.26°, 77.41°')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/forecast-runs/ifs-oper-test/precipitation/point/?lat=23.26&lon=77.41',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getByText('1.25 mm')).toBeInTheDocument();
  });
});
