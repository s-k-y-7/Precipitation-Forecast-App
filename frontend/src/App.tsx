import { useEffect, useMemo, useState } from 'react';
import { GeoJSON, MapContainer, Marker, TileLayer, ZoomControl, useMap, useMapEvents } from 'react-leaflet';
import { CitySearch } from './CitySearch';
import { fetchForecastRuns, fetchIndiaCoverage, fetchPointForecast, intervalTileUrl, type ForecastRun, type IndiaCoverage, type PlaceSearchResult, type PointForecast } from './api/forecasts';

const basemap = import.meta.env.VITE_BASEMAP_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const steps = [3, 6, 9, 12, 15, 18, 21, 24];
function formatUtc(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) + ' UTC'; }
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
  const [step, setStep] = useState(3);
  const [coverage, setCoverage] = useState<IndiaCoverage | null>(null);
  const [point, setPoint] = useState<PointForecast | null>(null);
  const [selection, setSelection] = useState<[number, number] | null>(null);
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
    fetchForecastRuns(controller.signal)
      .then((catalog) => {
        setRuns(catalog.runs);
        setLatestRunId(catalog.latest_run_id);
        setSelectedRunId(catalog.latest_run_id);
        setRunError(null);
      })
      .catch((cause: unknown) => {
        if (cause instanceof Error && cause.name !== 'AbortError') setRunError(cause.message);
      })
      .finally(() => setLoading(false));
    fetchIndiaCoverage(controller.signal)
      .then((geometry) => { setCoverage(geometry); setCoverageError(null); })
      .catch((cause: unknown) => {
        if (cause instanceof Error && cause.name !== 'AbortError') setCoverageError(cause.message);
      });
    return () => controller.abort();
  }, []);
  const selectedRun = runs.find(run => run.run_id === selectedRunId);
  const interval = point?.intervals.find(item => item.end_step_hours === step);
  const selectedRunSteps = useMemo(() => selectedRun?.available_steps_hours ?? steps, [selectedRun]);
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
  const choosePoint = (lat: number, lon: number) => {
    if (!coverage) {
      setPoint(null);
      setSelection(null);
      setLocationError(coverageError ?? 'India coverage is still loading. Try selecting the location again shortly.');
      return;
    }
    if (!pointInIndia(lon, lat, coverage)) {
      setPoint(null);
      setSelection(null);
      setPointError(null);
      setLocationError('This forecast currently covers India only. Choose a location within India.');
      return;
    }
    setLocationError(null);
    setPoint(null);
    setSelection([lat, lon]);
    if (!selectedRunId) setPointError('No validated forecast run is currently available.');
    else setPointError(null);
  };
  const chooseCity = (place: PlaceSearchResult) => {
    setMapTarget([place.latitude, place.longitude]);
    choosePoint(place.latitude, place.longitude);
  };
  const displayedErrors = [runError, coverageError, locationError, pointError].filter((message): message is string => Boolean(message));

  return <main className="app-shell">
    <header className="topbar"><div className="brand-lockup"><span className="brand-mark" aria-hidden="true">☁</span><div><p className="eyebrow">ECMWF IFS · INDIA</p><h1>Precipitation forecast</h1></div></div>
      <div className="topbar-controls"><CitySearch onSelect={chooseCity}/>
      <label className="run-control"><span>Forecast run</span><select aria-label="Forecast run" value={selectedRunId ?? ''} onChange={event => { setSelectedRunId(event.target.value); setPoint(null); setSelection(null); setLocationError(null); setPointError(null); setTileError(false); }} disabled={loading || runs.length === 0}>
        {runs.length === 0 && <option value="">{loading ? 'Loading forecast runs…' : runError ? 'Forecast runs unavailable' : 'No validated runs available'}</option>}{runs.map(run => <option key={run.run_id} value={run.run_id}>{run.run_id === latestRunId ? 'Latest · ' : ''}{formatUtc(run.initialization_time)}</option>)}
      </select></label></div></header>
    <section className="map-frame" aria-label="Interactive precipitation forecast map">
      <MapContainer center={[22.5, 82]} zoom={4} minZoom={3} maxZoom={9} maxBounds={[[4, 64], [40, 101]]} maxBoundsViscosity={0.8} zoomControl={false} scrollWheelZoom className="forecast-map">
        <ZoomControl position="bottomright"/><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url={basemap} maxZoom={19}/>
        {coverage && <GeoJSON data={coverage as GeoJSON.GeoJsonObject} style={{ color: '#1e6071', weight: 2, fillOpacity: 0 }} />}
        {selectedRun && selectedRunSteps.includes(step) && <TileLayer key={`${selectedRun.run_id}-${step}`} url={intervalTileUrl(selectedRun.run_id, step)} opacity={0.82} maxNativeZoom={8} maxZoom={9} zIndex={300} eventHandlers={{ tileerror: () => setTileError(true), tileload: () => setTileError(false) }} />}
        {selection && <Marker position={selection}/>}
        <MapNavigator target={mapTarget}/>
        <MapClickHandler onSelect={choosePoint}/>
      </MapContainer>
      <div className="map-heading"><p className="eyebrow">3-HOUR PRECIPITATION</p><h2>{selectedRun ? `+${step - 3} to +${step} hours` : 'Forecast map'}</h2><p>Precipitation during interval · millimetres</p></div>
      <div className="legend" aria-label="Precipitation legend, millimetres"><span className="legend-title">mm / 3h</span><div className="legend-scale">{['#bbdefb','#64b5f6','#1e88e5','#009688','#7cb342','#fdd835','#fb8c00','#e53935'].map(color => <span key={color} style={{ background: color }}/>)}</div><div className="legend-labels"><span>0.1</span><span>1</span><span>2.5</span><span>5</span><span>10</span><span>20</span><span>50</span><span>100+</span></div></div>
      {selectedRun && <div className="timeline-card"><div className="timeline-head"><strong>Forecast timeline</strong><span>Valid {formatUtc(new Date(new Date(selectedRun.initialization_time).getTime() + step * 3600000).toISOString())}</span></div><input aria-label="Forecast time step" type="range" min="0" max={selectedRunSteps.length - 1} step="1" value={Math.max(0, selectedRunSteps.indexOf(step))} onChange={event => setStep(selectedRunSteps[Number(event.target.value)])}/><div className="timeline-steps">{selectedRunSteps.map(item => <button type="button" aria-pressed={step === item} key={item} onClick={() => setStep(item)}>+{item}h</button>)}</div></div>}
      <aside className="point-card" aria-live="polite"><div className="point-card-heading"><div><p className="eyebrow">LOCATION FORECAST</p><strong>{point ? `Selected ${point.requested_location.lat.toFixed(2)}°, ${point.requested_location.lon.toFixed(2)}°` : 'Select a location'}</strong>{point && <small className="grid-point">Nearest grid point {point.grid_point.lat.toFixed(2)}°, {point.grid_point.lon.toFixed(2)}°</small>}</div>{point && <span>mm / 3h</span>}</div>
        {pointLoading && <p role="status">Loading point forecast…</p>}{point && !pointLoading && <><p className="point-current">{interval?.precipitation_mm == null ? 'Unavailable' : `${interval.precipitation_mm.toFixed(2)} mm`} <small>· +{step - 3} to +{step}h</small></p><div className="point-series">{point.intervals.map(item => <button type="button" key={item.end_step_hours} onClick={() => setStep(item.end_step_hours)} aria-pressed={item.end_step_hours === step} title={`+${item.end_step_hours}h: ${item.precipitation_mm == null ? 'unavailable' : item.precipitation_mm.toFixed(2) + ' mm'}`}><span>{item.precipitation_mm == null ? '—' : item.precipitation_mm.toFixed(1)}</span><i style={{ height: `${Math.max(2, Math.min(48, (item.precipitation_mm ?? 0) * 2))}px` }}/><small>+{item.end_step_hours}</small></button>)}</div></>}
        {!point && !pointLoading && <p className="point-hint">Click inside India to inspect precipitation at that location.</p>}
      </aside>
      {loading && <div className="status-card" role="status">Loading available forecast runs…</div>}{!loading && !runError && runs.length === 0 && <div className="status-card" role="status"><strong>No validated forecast runs are available.</strong><span>Run <code>python manage.py refresh_forecast_runs</code> after applying migrations.</span></div>}
      {displayedErrors.length > 0 && <div className="tile-error" role="alert">{displayedErrors.join(' · ')}</div>}
      {tileError && <div className="tile-error" role="alert">Forecast tiles could not be loaded. The run may have expired or its source is temporarily unavailable.</div>}
      {selectedRun && <div className="run-caption">ECMWF Open Data · CC BY 4.0 · initialized {formatUtc(selectedRun.initialization_time)} · interval valid {formatUtc(new Date(new Date(selectedRun.initialization_time).getTime() + step * 3600000).toISOString())}</div>}
    </section>
  </main>;
}
