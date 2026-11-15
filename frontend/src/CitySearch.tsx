import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { searchPlaces, type PlaceSearchResult } from './api/forecasts';

type CitySearchProps = {
  onSelect: (place: PlaceSearchResult) => void;
};

export function CitySearch({ onSelect }: CitySearchProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlaceSearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const selectedQuery = useRef<string | null>(null);

  useEffect(() => {
    if (selectedQuery.current === query) {
      setLoading(false);
      return;
    }
    if (query.trim().length < 2) {
      setLoading(false);
      setResults([]);
      setActiveIndex(-1);
      return;
    }

    const currentRequest = requestId.current;
    const requestController = new AbortController();
    controller.current = requestController;
    setLoading(true);
    setError(null);
    const timer = window.setTimeout(() => {
      searchPlaces(query, requestController.signal)
        .then(response => {
          if (requestId.current !== currentRequest) return;
          setResults(response.results);
          setActiveIndex(-1);
          setOpen(true);
        })
        .catch(cause => {
          if (requestId.current !== currentRequest || requestController.signal.aborted) return;
          setError(cause instanceof Error ? cause.message : 'City search failed.');
          setResults([]);
          setOpen(true);
        })
        .finally(() => {
          if (requestId.current === currentRequest) setLoading(false);
        });
    }, 250);

    return () => {
      requestId.current += 1;
      window.clearTimeout(timer);
      requestController.abort();
      if (controller.current === requestController) controller.current = null;
    };
  }, [query]);

  const choose = (place: PlaceSearchResult) => {
    requestId.current += 1;
    controller.current?.abort();
    controller.current = null;
    selectedQuery.current = place.name;
    setQuery(place.name);
    setResults([]);
    setActiveIndex(-1);
    setOpen(false);
    setLoading(false);
    setError(null);
    onSelect(place);
  };

  const handleChange = (value: string) => {
    requestId.current += 1;
    controller.current?.abort();
    controller.current = null;
    selectedQuery.current = null;
    setQuery(value);
    setResults([]);
    setActiveIndex(-1);
    setOpen(true);
    setLoading(value.trim().length >= 2);
    setError(null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      requestId.current += 1;
      controller.current?.abort();
      controller.current = null;
      setOpen(false);
      setResults([]);
      setActiveIndex(-1);
      setLoading(false);
    } else if (event.key === 'ArrowDown' && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(index => (index < 0 ? 0 : (index + 1) % results.length));
    } else if (event.key === 'ArrowUp' && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(index => (index <= 0 ? results.length - 1 : index - 1));
    } else if (event.key === 'Enter' && open && results.length > 0) {
      event.preventDefault();
      choose(results[activeIndex < 0 ? 0 : activeIndex]);
    }
  };

  const showMessage = open && query.trim().length >= 2;

  return <div className="city-search">
    <label htmlFor="city-search-input">Find a city in India</label>
    <input
      id="city-search-input"
      type="search"
      role="combobox"
      aria-label="Search Indian city"
      aria-autocomplete="list"
      aria-expanded={open && results.length > 0}
      aria-controls="city-search-results"
      aria-activedescendant={open && activeIndex >= 0 ? `city-search-option-${results[activeIndex]?.id}` : undefined}
      placeholder="Search city or town"
      autoComplete="off"
      value={query}
      onChange={event => handleChange(event.target.value)}
      onKeyDown={handleKeyDown}
      onFocus={() => { if (results.length || loading || error) setOpen(true); }}
      onBlur={() => setOpen(false)}
    />
    {showMessage && <div className="city-search-popover">
      {loading && <p className="city-search-message" role="status">Searching Indian cities…</p>}
      {!loading && error && <p className="city-search-message city-search-error" role="alert">{error}</p>}
      {!loading && !error && results.length === 0 && <p className="city-search-message" role="status">No matching Indian cities found.</p>}
      {results.length > 0 && <ul id="city-search-results" role="listbox" aria-label="Indian city search results">
        {results.map((place, index) => <li
          id={`city-search-option-${place.id}`}
          key={place.id}
          role="option"
          aria-selected={index === activeIndex}
          onMouseDown={event => event.preventDefault()}
          onClick={() => choose(place)}
        >
          <span>{place.name}</span><small>{place.admin1}</small>
        </li>)}
      </ul>}
      <p className="city-search-credit">Place data © <a href="https://www.geonames.org/" target="_blank" rel="noreferrer">GeoNames</a> · CC BY 4.0</p>
    </div>}
  </div>;
}
