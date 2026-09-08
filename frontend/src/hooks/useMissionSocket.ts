import { useCallback, useEffect, useRef, useState } from 'react';
import type { BackendMessage, LatLng, MissionPlan, TelemetryData } from '../types';

const WS_URL = import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000/ws/frontend';

export function useMissionSocket() {
  const [connected, setConnected] = useState(false);
  const [missionPlan, setMissionPlan] = useState<MissionPlan | null>(null);
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | undefined>(undefined);
  const disposedRef = useRef(false);
  // Retains the inputs that produced the current plan. This supports a
  // rolling deployment where a browser reaches an older backend briefly.
  const requestedSettingsRef = useRef({ rowSpacing: 1.0, samplingSpacing: 3.0 });

  useEffect(() => {
    disposedRef.current = false;
    const connect = () => {
      if (disposedRef.current) return;
      const socket = new WebSocket(WS_URL);
      socketRef.current = socket;
      socket.onopen = () => { setConnected(true); setError(null); };
      socket.onclose = () => {
        setConnected(false);
        if (!disposedRef.current) reconnectRef.current = window.setTimeout(connect, 3000);
      };
      socket.onerror = () => setError('Backend connection unavailable. Check the server and WebSocket URL.');
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as BackendMessage;
          if (message.type === 'MISSION_STARTED') {
            const requested = requestedSettingsRef.current;
            setMissionPlan({
              ...message.plan,
              row_spacing_m: Number.isFinite(message.plan.row_spacing_m) ? message.plan.row_spacing_m : requested.rowSpacing,
              sampling_density_m: Number.isFinite(message.plan.sampling_density_m) ? message.plan.sampling_density_m : requested.samplingSpacing,
            });
            setError(null);
          }
          if (message.type === 'MISSION_ERROR') setError(message.error || 'The backend rejected this mission.');
          if (message.type === 'TELEMETRY') setTelemetry(message.payload);
        } catch { setError('Received an unreadable message from the backend.'); }
      };
    };
    connect();
    return () => {
      disposedRef.current = true;
      if (reconnectRef.current) window.clearTimeout(reconnectRef.current);
      socketRef.current?.close();
    };
  }, []);

  const startMission = useCallback((boundaryPoints: LatLng[], payload: string, prescription: Record<string, number>, rowSpacing: number, samplingSpacing: number) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) { setError('Backend is offline. Mission was not sent.'); return false; }
    requestedSettingsRef.current = { rowSpacing, samplingSpacing };
    socketRef.current.send(JSON.stringify({
      type: 'START_MISSION',
      payload: {
        field_id: 'field_alpha',
        boundary_points: boundaryPoints,
        row_spacing_m: rowSpacing,
        sampling_density_m: samplingSpacing,
        active_payload: payload,
        prescription,
      },
    }));
    setError(null);
    return true;
  }, []);

  const stopMission = useCallback(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify({ type: 'STOP_MISSION' }));
  }, []);

  const resetMission = useCallback(() => {
    setMissionPlan(null);
    setTelemetry(null);
    setError(null);
  }, []);

  return { connected, missionPlan, telemetry, error, startMission, stopMission, resetMission };
}
