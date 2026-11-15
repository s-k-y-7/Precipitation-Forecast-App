import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CitySearch } from './CitySearch';
import { searchPlaces } from './api/forecasts';

vi.mock('./api/forecasts', () => ({ searchPlaces: vi.fn() }));

const place = (id: number, name: string) => ({
  id, name, admin1: 'Test State', latitude: 23.26, longitude: 77.41, population: 100000,
});

describe('city search', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks(); });

  it('ignores an older response that resolves after a newer query', async () => {
    let resolveFirst!: (value: { results: ReturnType<typeof place>[] }) => void;
    let resolveSecond!: (value: { results: ReturnType<typeof place>[] }) => void;
    vi.mocked(searchPlaces)
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve; }));
    render(<CitySearch onSelect={vi.fn()} />);
    const input = screen.getByRole('combobox', { name: 'Search Indian city' });

    fireEvent.change(input, { target: { value: 'delhi' } });
    await act(async () => { vi.advanceTimersByTime(250); await Promise.resolve(); });
    fireEvent.change(input, { target: { value: 'mumbai' } });
    await act(async () => { vi.advanceTimersByTime(250); await Promise.resolve(); });

    await act(async () => { resolveSecond({ results: [place(2, 'Mumbai')] }); await Promise.resolve(); });
    expect(screen.getByRole('option', { name: /Mumbai/ })).toBeInTheDocument();
    await act(async () => { resolveFirst({ results: [place(1, 'Delhi')] }); await Promise.resolve(); });
    expect(screen.getByRole('option', { name: /Mumbai/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /Delhi/ })).not.toBeInTheDocument();
  });

  it('selects the highlighted result with the keyboard', async () => {
    vi.mocked(searchPlaces).mockResolvedValue({ results: [place(3, 'Bhopal')] });
    const onSelect = vi.fn();
    render(<CitySearch onSelect={onSelect} />);
    const input = screen.getByRole('combobox', { name: 'Search Indian city' });
    fireEvent.change(input, { target: { value: 'bhopal' } });
    await act(async () => { vi.advanceTimersByTime(250); await Promise.resolve(); });
    expect(screen.getByRole('option', { name: /Bhopal/ })).toBeInTheDocument();
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(onSelect).toHaveBeenCalledWith(place(3, 'Bhopal'));
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});
