import { useEffect, useMemo, useState } from 'react';
import { GeoJSON, MapContainer, Marker, TileLayer, ZoomControl, useMap, useMapEvents } from 'react-leaflet';
import { CitySearch } from './CitySearch';
import { fetchForecastRuns, fetchIndiaCoverage, fetchIntervalOverview, fetchPointForecast, intervalTileUrl, type ForecastRun, type IndiaCoverage, type IntervalOverview, type PlaceSearchResult, type PointForecast } from './api/forecasts';
import { formatRunTimestamp, formatTimelineTimestamp, type DisplayTimezone } from './time';

const basemap = import.meta.env.VITE_BASEMAP_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const steps = [3, 6, 9, 12, 15, 18, 21, 24];
const RUN_CATALOG_REFRESH_INTERVAL_MS = 5 * 60 * 1000;
export function complete24HourTotal(point: PointForecast | null): number | null {
  if (!point || point.intervals.length !== steps.length) return null;
  if (point.intervals.some((interval, index) =>
    interval.start_step_hours !== steps[index] - 3 || interval.end_step_hours !== steps[index] ||
    interval.precipitation_mm === null || !Number.isFinite(interval.precipitation_mm))) {
    return null;
  }
  return point.intervals.reduce((total, interval) => total + (interval.precipitation_mm ?? 0), 0);
}

function insideRing(point: [number, number], ring: number[][]) {
  const [x, y] = point; let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]; const [xj, yj] = ring[j];
    if (((yi > y) !== (yj > y)) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function pointInIndia(lon: number, lat: number, coverage: IndiaCoverage | null) {
  if (!coverage) return false;
  const polygons: number[][][][] = [];
  const add = (geometry: GeoJSON.Geometry | null) => {
    if (!geometry) return;
    if (geometry.type === 'Polygon') polygons.push(geometry.coordinates as number[][][]);
    if (geometry.type === 'MultiPolygon') polygons.push(...geometry.coordinates as number[][][][]);
    if (geometry.type === 'GeometryCollection') geometry.geometries.forEach(add);
  };
  if ('type' in coverage && coverage.type === 'FeatureCollection') coverage.features.forEach(f => add(f.geometry));
  else if (coverage.type === 'Feature') add(coverage.geometry);
  else add(coverage as GeoJSON.Geometry);
  return polygons.some(polygon => insideRing([lon, lat], polygon[0]) && !polygon.slice(1).some(hole => insideRing([lon, lat], hole)));
}
function MapClickHandler({ onSelect }: { onSelect: (lat: number, lon: number) => void }) {
  useMapEvents({ click: event => onSelect(event.latlng.lat, event.latlng.lng) });
  return null;
}

function MapNavigator({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, 8, { duration: 0.7 });
  }, [map, target]);
  return null;
}

export function App() {
  const [runs, setRuns] = useState<ForecastRun[]>([]);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [displayTimezone, setDisplayTimezone] = useState<DisplayTimezone>('Asia/Kolkata');
  const [step, setStep] = useState(3);
  const [coverage, setCoverage] = useState<IndiaCoverage | null>(null);
  const [point, setPoint] = useState<PointForecast | null>(null);
  const [selection, setSelection] = useState<[number, number] | null>(null);
  const [selectedCityName, setSelectedCityName] = useState<string | null>(null);
  const [overview, setOverview] = useState<IntervalOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [mapTarget, setMapTarget] = useState<[number, number] | null>(null);
  const [loading, setLoading] = useState(true);
  const [pointLoading, setPointLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [coverageError, setCoverageError] = useState<string | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [pointError, setPointError] = useState<string | null>(null);
  const [tileError, setTileError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let requestPending = false;
    const refreshRunCatalog = () => {
      if (requestPending) return;
      requestPending = true;
      fetchForecastRuns(controller.signal)
        .then((catalog) => {
          setRuns(catalog.runs);
          setLatestRunId(catalog.latest_run_id);
          setSelectedRunId(current => current && catalog.runs.some(run => run.run_id === current)
            ? current
            : catalog.latest_run_id);
          setRunError(null);
        })
        .catch((cause: unknown) => {
          if (cause instanceof Error && cause.name !== 'AbortError') setRunError(cause.message);
        })
        .finally(() => {
          requestPending = false;
          if (!controller.signal.aborted) setLoading(false);
        });
    };
    refreshRunCatalog();
    const catalogPoll = window.setInterval(refreshRunCatalog, RUN_CATALOG_REFRESH_INTERVAL_MS);
    fetchIndiaCoverage(controller.signal)
      .then((geometry) => { setCoverage(geometry); setCoverageError(null); })
      .catch((cause: unknown) => {
        if (cause instanceof Error && cause.name !== 'AbortError') setCoverageError(cause.message);
      });
    return () => {
      window.clearInterval(catalogPoll);
      controller.abort();
    };
  }, []);
  const selectedRun = runs.find(run => run.run_id === selectedRunId);
  const interval = point?.intervals.find(item => item.end_step_hours === step);
  const currentOverview = overview?.run_id === selectedRunId && overview.end_step_hours === step ? overview : null;
  const pointTotal = complete24HourTotal(point);
  const selectedRunSteps = useMemo(() => selectedRun?.available_steps_hours ?? steps, [selectedRun]);
  useEffect(() => {
    if (selection || !selectedRunId) {
      setOverview(null);
      setOverviewLoading(false);
      setOverviewError(null);
      return;
    }
    const controller = new AbortController();
    setOverview(null);
    setOverviewLoading(true);
    setOverviewError(null);
    fetchIntervalOverview(selectedRunId, step, controller.signal)
      .then(setOverview)
      .catch(cause => {
        if (cause instanceof Error && cause.name !== 'AbortError') setOverviewError(cause.message);
      })
      .finally(() => { if (!controller.signal.aborted) setOverviewLoading(false); });
    return () => controller.abort();
  }, [selection, selectedRunId, step]);
  useEffect(() => {
    if (!selection || !selectedRunId) { setPointLoading(false); return; }
    const controller = new AbortController();
    setPointLoading(true); setPointError(null);
    fetchPointForecast(selectedRunId, selection[0], selection[1], controller.signal)
      .then(setPoint)
      .catch(cause => { if (cause instanceof Error && cause.name !== 'AbortError') setPointError(cause.message); })
      .finally(() => { if (!controller.signal.aborted) setPointLoading(false); });
    return () => controller.abort();
  }, [selection, selectedRunId]);
  const choosePoint = (lat: number, lon: number, cityName: string | null = null) => {
    if (!coverage) {
      setPoint(null);
      setSelection(null);
      setSelectedCityName(null);
      setLocationError(coverageError ?? 'India coverage is still loading. Try selecting the location again shortly.');
      return;
    }
    if (!pointInIndia(lon, lat, coverage)) {
      setPoint(null);
      setSelection(null);
      setSelectedCityName(null);
      setPointError(null);
      setLocationError('This forecast currently covers India only. Choose a location within India.');
      return;
    }
    setLocationError(null);
    setPoint(null);
    setSelection([lat, lon]);
    setSelectedCityName(cityName);
    if (!selectedRunId) setPointError('No validated forecast run is currently available.');
    else setPointError(null);
  };
  const chooseCity = (place: PlaceSearchResult) => {
    setMapTarget([place.latitude, place.longitude]);
    choosePoint(place.latitude, place.longitude, place.name);
  };
  const displayedErrors = [runError, coverageError, locationError, pointError].filter((message): message is string => Boolean(message));

  return <main className="app-shell">
    <header className="topbar"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 48 48" focusable="false"><path d="M14 29.5a7.5 7.5 0 0 1 .9-15 10.5 10.5 0 0 1 19.8 2.8A6.4 6.4 0 0 1 34 30H14Z"/><path d="m18 35-2 4m12-4-2 4m12-4-2 4"/></svg></span><div><p className="eyebrow">ECMWF IFS · India</p><h1>Precipitation Forecast</h1></div></div>
      <div className="topbar-controls"><CitySearch onSelect={chooseCity}/>
      <label className="run-control"><span>Forecast run</span><select aria-label="Forecast run" value={selectedRunId ?? ''} onChange={event => { setSelectedRunId(event.target.value); setPoint(null); setSelection(null); setSelectedCityName(null); setLocationError(null); setPointError(null); setTileError(false); }} disabled={loading || runs.length === 0}>
        {runs.length === 0 && <option value="">{loading ? 'Loading forecast runs…' : runError ? 'Forecast runs unavailable' : 'No validated runs available'}</option>}{runs.map(run => <option key={run.run_id} value={run.run_id}>{run.run_id === latestRunId ? 'Latest forecast run' : formatRunTimestamp(run.initialization_time, displayTimezone)}</option>)}
      </select></label>
      <div className="timezone-control"><span className="timezone-label">Timezone</span><div className="timezone-toggle" role="group" aria-label="Display timezone"><button type="button" aria-pressed={displayTimezone === 'Asia/Kolkata'} onClick={() => setDisplayTimezone('Asia/Kolkata')}>IST</button><button type="button" aria-pressed={displayTimezone === 'UTC'} onClick={() => setDisplayTimezone('UTC')}>UTC</button></div></div></div></header>
    <div className="forecast-layout">
      <div className="map-column">
    <section className="map-frame" aria-label="Interactive precipitation forecast map">
      <div className="map-panel-header"><h2>Forecast Map</h2></div>
      <div className="map-canvas">
      <MapContainer center={[22.5, 82]} zoom={4.5} zoomSnap={0.5} minZoom={3} maxZoom={9} maxBounds={[[4, 64], [40, 101]]} maxBoundsViscosity={0.8} zoomControl={false} scrollWheelZoom className="forecast-map">
        <ZoomControl position="bottomright"/><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url={basemap} maxZoom={19}/>
        {coverage && <GeoJSON data={coverage as GeoJSON.GeoJsonObject} style={{ color: '#63818a', weight: 1.5, opacity: 0.78, fillOpacity: 0 }} />}
        {selectedRun && selectedRunSteps.includes(step) && <TileLayer key={`${selectedRun.run_id}-${step}`} url={intervalTileUrl(selectedRun.run_id, step)} opacity={0.82} maxNativeZoom={8} maxZoom={9} zIndex={300} eventHandlers={{ tileerror: () => setTileError(true), tileload: () => setTileError(false) }} />}
        {selection && <Marker position={selection}/>}
        <MapNavigator target={mapTarget}/>
        <MapClickHandler onSelect={choosePoint}/>
      </MapContainer>
      <div className="legend" aria-label="Precipitation legend, millimetres"><span className="legend-title">mm / 3h</span><div className="legend-scale">{['#bbdefb','#64b5f6','#1e88e5','#009688','#7cb342','#fdd835','#fb8c00','#e53935'].map(color => <span key={color} style={{ background: color }}/>)}</div><div className="legend-labels"><span>0.1</span><span>1</span><span>2.5</span><span>5</span><span>10</span><span>20</span><span>50</span><span>100+</span></div></div>
      {loading && <div className="status-card" role="status">Loading available forecast runs…</div>}{!loading && !runError && runs.length === 0 && <div className="status-card" role="status"><strong>No validated forecast runs are available.</strong><span>Run <code>python manage.py refresh_forecast_runs</code> after applying migrations.</span></div>}
      {displayedErrors.length > 0 && <div className="tile-error" role="alert">{displayedErrors.join(' · ')}</div>}
      {tileError && <div className="tile-error" role="alert">Forecast tiles could not be loaded. The run may have expired or its source is temporarily unavailable.</div>}
      </div>
    </section>
      {selectedRun && <div className="timeline-card"><div className="timeline-head"><h2>Forecast Timeline</h2><span>{formatTimelineTimestamp(new Date(new Date(selectedRun.initialization_time).getTime() + step * 3600000).toISOString(), displayTimezone)}</span></div><div className="timeline-steps">{selectedRunSteps.map(item => <button type="button" aria-pressed={step === item} key={item} onClick={() => setStep(item)}>+{item}h</button>)}</div></div>}
      </div>
      <aside className={`forecast-sidebar${selection ? ' has-selection' : ''}`} aria-label={selection ? 'Location forecast' : 'India-wide forecast overview'} aria-live="polite">
        {!selection && <section className="sidebar-section overview-section">
          <div className="sidebar-heading"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19v-5h4v5H4Zm6 0V9h4v10h-4Zm6 0V4h4v15h-4Z"/></svg><h2>India-wide Overview</h2></div>
          {overviewLoading && <p role="status">Calculating India grid overview…</p>}
          {!overviewLoading && overviewError && <p className="point-hint" role="alert">{overviewError}</p>}
          {!overviewLoading && !overviewError && currentOverview && typeof currentOverview.max_precipitation_mm === 'number' && Number.isFinite(currentOverview.max_precipitation_mm) && <><p className="point-current">{currentOverview.max_precipitation_mm.toFixed(2)} mm</p><p className="overview-label">Maximum gridpoint precipitation</p></>}
          {!overviewLoading && !overviewError && currentOverview && !(typeof currentOverview.max_precipitation_mm === 'number' && Number.isFinite(currentOverview.max_precipitation_mm)) && <p className="point-hint">No valid forecast grid values are available for this interval.</p>}
          {!overviewLoading && !overviewError && !currentOverview && selectedRun && <p className="point-hint">Loading overview for this interval…</p>}
          <div className="overview-note"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg><span>No reliable land-area percentage for this forecast run.</span></div>
        </section>}
        <section className="sidebar-section location-section">
          <div className="sidebar-heading"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 10c0 5-7 12-7 12S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/></svg><h2>Location Forecast</h2></div>
          {selection ? <>
            <div className="location-summary"><strong>{selectedCityName ?? 'Selected map location'}</strong><span>{selection[0].toFixed(4)}°, {selection[1].toFixed(4)}°</span>{point && <small>Nearest ECMWF grid point {point.grid_point.lat.toFixed(2)}°, {point.grid_point.lon.toFixed(2)}°</small>}</div>
            {pointLoading && <p role="status">Loading point forecast…</p>}
            {point && !pointLoading && <><div className="selected-interval"><strong>{interval?.precipitation_mm == null ? 'Unavailable' : `${interval.precipitation_mm.toFixed(2)} mm`}</strong><small>+{step - 3} to +{step}h precipitation · Valid {interval ? formatTimelineTimestamp(interval.valid_time, displayTimezone) : ''}</small></div>{pointTotal !== null && <p className="point-total">24-hour total <strong>{pointTotal.toFixed(2)} mm</strong></p>}<div className="point-series">{point.intervals.map(item => <button type="button" key={item.end_step_hours} onClick={() => setStep(item.end_step_hours)} aria-pressed={item.end_step_hours === step} title={`+${item.end_step_hours}h · ${formatTimelineTimestamp(item.valid_time, displayTimezone)}: ${item.precipitation_mm == null ? 'unavailable' : item.precipitation_mm.toFixed(2) + ' mm'}`}><span>{item.precipitation_mm == null ? '—' : item.precipitation_mm.toFixed(1)}</span><i style={{ height: `${Math.max(2, Math.min(48, (item.precipitation_mm ?? 0) * 2))}px` }}/><small>+{item.end_step_hours}</small></button>)}</div></>}
            {!point && !pointLoading && <p className="point-hint">{pointError ?? 'Forecast values are not available for this location.'}</p>}
          </> : <p className="location-prompt">Search for a city or click on the map to see point forecast.</p>}
        </section>
        <section className="sidebar-section about-section"><div className="sidebar-heading"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg><h2>About This Data</h2></div><p>Data: ECMWF IFS, 0.25° × 0.25°</p><p>Source: ECMWF Open Data</p><a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC BY 4.0 ↗</a></section>
      </aside>
    </div>
  </main>;
}
