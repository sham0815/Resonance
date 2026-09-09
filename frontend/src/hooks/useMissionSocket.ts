import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';

import type {
  BackendMessage,
  LatLng,
  MissionPlan,
  SoilMoisturePrediction,
  TelemetryData,
  Payload,
} from '../types';

const WS_URL =
  import.meta.env.VITE_BACKEND_WS_URL ||
  'ws://localhost:8000/ws/frontend';

export function useMissionSocket() {
  const [connected, setConnected] = useState(false);

  const [missionPlan, setMissionPlan] =
    useState<MissionPlan | null>(null);

  const [missionPaused, setMissionPaused] =
    useState(false);

  const [telemetry, setTelemetry] =
    useState<TelemetryData | null>(null);

  const [telemetryHistory, setTelemetryHistory] =
    useState<TelemetryData[]>([]);

  const [predictions, setPredictions] =
    useState<SoilMoisturePrediction[]>([]);

  const [error, setError] =
    useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);

  const reconnectRef =
    useRef<number | undefined>(undefined);

  const disposedRef = useRef(false);

  const requestedSettingsRef = useRef({
    rowSpacing: 1.0,
    samplingSpacing: 3.0,
  });

  useEffect(() => {
    disposedRef.current = false;

    const connect = () => {
      if (disposedRef.current) return;

      const socket = new WebSocket(WS_URL);

      socketRef.current = socket;

      socket.onopen = () => {
        setConnected(true);
        setError(null);
      };

      socket.onclose = () => {
        setConnected(false);

        if (!disposedRef.current) {
          reconnectRef.current = window.setTimeout(
            connect,
            3000
          );
        }
      };

      socket.onerror = () => {
        setError(
          'Backend connection unavailable. Check the server and WebSocket URL.'
        );
      };

      socket.onmessage = (event) => {
        try {
          const message =
            JSON.parse(event.data) as BackendMessage;

          if (message.type === 'MISSION_STARTED') {
            const requested =
              requestedSettingsRef.current;

            setMissionPlan({
              ...message.plan,

              row_spacing_m: Number.isFinite(
                message.plan.row_spacing_m
              )
                ? message.plan.row_spacing_m
                : requested.rowSpacing,

              sampling_density_m: Number.isFinite(
                message.plan.sampling_density_m
              )
                ? message.plan.sampling_density_m
                : requested.samplingSpacing,
            });

            setMissionPaused(false);
            setError(null);
          }

          if (message.type === 'MISSION_PAUSED') {
            setMissionPaused(true);
          }

          if (message.type === 'MISSION_RESUMED') {
            setMissionPaused(false);
          }

          if (message.type === 'MISSION_STOPPED') {
            setMissionPaused(false);
          }

          if (message.type === 'MISSION_ERROR') {
            setError(
              message.error ||
              'The backend rejected this mission.'
            );
          }

          if (message.type === 'TELEMETRY') {
            setTelemetry(message.payload);

            setTelemetryHistory((history) =>
              [...history, message.payload].slice(-300)
            );
          }

          if (
            message.type ===
            'AI_SOIL_MOISTURE_PREDICTION'
          ) {
            setPredictions((items) =>
              [...items, message.payload].slice(-300)
            );
          }
        } catch {
          setError(
            'Received an unreadable message from the backend.'
          );
        }
      };
    };

    connect();

    return () => {
      disposedRef.current = true;

      if (reconnectRef.current) {
        window.clearTimeout(reconnectRef.current);
      }

      socketRef.current?.close();
    };
  }, []);

  const startMission = useCallback(
    (
      boundaryPoints: LatLng[],
      payload: Payload,
      prescription: Record<string, number>,
      soilType: string = 'loam',
      rowSpacing: number = 1.0,
      samplingSpacing: number = 3.0
    ) => {
      if (
        socketRef.current?.readyState !==
        WebSocket.OPEN
      ) {
        setError(
          'Backend is offline. Mission was not sent.'
        );

        return false;
      }

      requestedSettingsRef.current = {
        rowSpacing,
        samplingSpacing,
      };

      socketRef.current.send(
        JSON.stringify({
          type: 'START_MISSION',

          payload: {
            field_id: 'field_alpha',
            boundary_points: boundaryPoints,
            row_spacing_m: rowSpacing,
            sampling_density_m: samplingSpacing,
            active_payload: payload,
            prescription,
            soil_type: soilType,
          },
        })
      );

      setMissionPaused(false);
      setError(null);

      return true;
    },
    []
  );

  const stopMission = useCallback(() => {
    if (
      socketRef.current?.readyState ===
      WebSocket.OPEN
    ) {
      socketRef.current.send(
        JSON.stringify({
          type: 'STOP_MISSION',
        })
      );
    }

    setMissionPaused(false);
  }, []);

  const pauseMission = useCallback(() => {
    if (
      socketRef.current?.readyState ===
      WebSocket.OPEN
    ) {
      socketRef.current.send(
        JSON.stringify({
          type: 'PAUSE_MISSION',
        })
      );

      // Immediately change Stop -> Resume
      setMissionPaused(true);
    }
  }, []);

  const resumeMission = useCallback(() => {
    if (
      socketRef.current?.readyState ===
      WebSocket.OPEN
    ) {
      socketRef.current.send(
        JSON.stringify({
          type: 'RESUME_MISSION',
        })
      );

      // Immediately change Resume -> Stop
      setMissionPaused(false);
    }
  }, []);

  const resetMission = useCallback(() => {
    setMissionPlan(null);
    setMissionPaused(false);
    setTelemetry(null);
    setTelemetryHistory([]);
    setPredictions([]);
    setError(null);
  }, []);

  return {
    connected,
    missionPlan,
    missionPaused,
    telemetry,
    telemetryHistory,
    predictions,
    error,
    startMission,
    stopMission,
    pauseMission,
    resumeMission,
    resetMission,
  };
}