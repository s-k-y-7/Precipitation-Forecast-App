import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet';
import { fetchForecastRuns, precipitationTileUrl, type ForecastRun } from './api/forecasts';

const basemap = import.meta.env.VITE_BASEMAP_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

function formatRun(run: ForecastRun): string {
  const date = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(run.initialization_time));
  return `${date} UTC · +${run.lead_hours}h`;
}

export function App() {
  const [runs, setRuns] = useState<ForecastRun[]>([]);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tileError, setTileError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchForecastRuns(controller.signal)
      .then((catalog) => {
        setRuns(catalog.runs);
        setLatestRunId(catalog.latest_run_id);
        setSelectedRunId((current) => current ?? catalog.latest_run_id);
      })
      .catch((cause: unknown) => {
        if (cause instanceof Error && cause.name !== 'AbortError') setError(cause.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const selectedRun = runs.find((run) => run.run_id === selectedRunId);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">☁</span>
          <div>
            <p className="eyebrow">ECMWF IFS · INDIA</p>
            <h1>Precipitation forecast</h1>
          </div>
        </div>
        <label className="run-control">
          <span>Forecast run</span>
          <select
            aria-label="Forecast run"
            value={selectedRunId ?? ''}
            onChange={(event) => {
              setTileError(false);
              setSelectedRunId(event.target.value);
            }}
            disabled={loading || runs.length === 0}
          >
            {runs.length === 0 && <option value="">No recent runs available</option>}
            {runs.map((run) => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id === latestRunId ? 'Latest · ' : ''}{formatRun(run)}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="map-frame" aria-label="Interactive precipitation forecast map">
        <MapContainer
          center={[22.5, 82]}
          zoom={4}
          minZoom={3}
          maxZoom={9}
          maxBounds={[[4, 64], [40, 101]]}
          maxBoundsViscosity={0.8}
          zoomControl={false}
          scrollWheelZoom
          className="forecast-map"
        >
          <ZoomControl position="bottomright" />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
            url={basemap}
            maxZoom={19}
          />
          {selectedRun && (
            <TileLayer
              key={selectedRun.run_id}
              url={precipitationTileUrl(selectedRun.run_id)}
              opacity={0.82}
              bounds={[[6, 68], [37.5, 97.5]]}
              maxNativeZoom={8}
              maxZoom={9}
              zIndex={300}
              eventHandlers={{
                tileerror: () => setTileError(true),
                tileload: () => setTileError(false),
              }}
            />
          )}
        </MapContainer>

        <div className="map-heading">
          <p className="eyebrow">TOTAL PRECIPITATION</p>
          <h2>{selectedRun ? `Next ${selectedRun.lead_hours} hours` : 'Forecast map'}</h2>
          <p>Accumulated precipitation · millimetres</p>
        </div>

        <div className="legend" aria-label="Precipitation legend, millimetres">
          <span className="legend-title">mm</span>
          <div className="legend-scale">
            <span style={{ background: '#bbdefb' }} />
            <span style={{ background: '#64b5f6' }} />
            <span style={{ background: '#1e88e5' }} />
            <span style={{ background: '#009688' }} />
            <span style={{ background: '#7cb342' }} />
            <span style={{ background: '#fdd835' }} />
            <span style={{ background: '#fb8c00' }} />
            <span style={{ background: '#e53935' }} />
          </div>
          <div className="legend-labels"><span>0.1</span><span>1</span><span>2.5</span><span>5</span><span>10</span><span>20</span><span>50</span><span>100+</span></div>
        </div>

        {loading && <div className="status-card" role="status">Loading available forecast runs…</div>}
        {!loading && error && <div className="status-card status-error" role="alert">{error}</div>}
        {!loading && !error && runs.length === 0 && (
          <div className="status-card" role="status">
            <strong>No forecast runs are registered yet.</strong>
            <span>Start the backend and run <code>python manage.py refresh_forecast_runs</code>.</span>
          </div>
        )}
        {tileError && (
          <div className="tile-error" role="alert">
            Forecast tiles could not be loaded. The run may have expired or its source is temporarily unavailable.
          </div>
        )}
        {selectedRun && (
          <div className="run-caption">
            ECMWF Open Data · CC BY 4.0 · initialized {formatRun(selectedRun).replace(` · +${selectedRun.lead_hours}h`, '')} · valid {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(selectedRun.valid_time))} UTC
          </div>
        )}
      </section>
    </main>
  );
}
