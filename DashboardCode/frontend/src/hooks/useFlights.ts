import { useState, useCallback } from 'react';

export interface Flight {
  flight_id: string;
  created_at: string;
  status: string;
  label: string;
  mission_type: string;
  notes: string;
  started_at?: string;
  stopped_at?: string;
}

export function useFlights() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [loading, setLoading] = useState(false);
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchFlights = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/flights`);
      if (response.ok) {
        const data = await response.json();
        setFlights(data);
      }
    } catch (e) {
      console.error('Failed to fetch flights:', e);
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  const createFlight = useCallback(async (label: string, mission: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/flights?label=${label}&mission_type=${mission}`, {
        method: 'POST',
      });
      if (response.ok) {
        const data = await response.json();
        await fetchFlights();
        return data;
      }
    } catch (e) {
      console.error('Failed to create flight:', e);
    }
  }, [API_BASE, fetchFlights]);

  const startFlight = useCallback(async (flightId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/flights/${flightId}/start`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchFlights();
        return true;
      }
    } catch (e) {
      console.error('Failed to start flight:', e);
    }
    return false;
  }, [API_BASE, fetchFlights]);

  const stopFlight = useCallback(async (flightId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/flights/${flightId}/stop`, {
        method: 'POST',
      });
      if (response.ok) {
        await fetchFlights();
        return true;
      }
    } catch (e) {
      console.error('Failed to stop flight:', e);
    }
    return false;
  }, [API_BASE, fetchFlights]);

  return {
    flights,
    loading,
    fetchFlights,
    createFlight,
    startFlight,
    stopFlight,
  };
}
