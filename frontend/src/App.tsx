import { useEffect, useMemo, useState } from 'react';
import type { LeafletMouseEvent } from 'leaflet';
import { ConnectionBadge } from './components/ConnectionBadge';
import MapPanel from './components/MapPanel';
import { MissionPanel } from './components/MissionPanel';
import { ResourcesPanel } from './components/ResourcesPanel';
import { TelemetryPanel } from './components/TelemetryPanel';
import { TemporaryEsp32StatusPanel } from './components/TemporaryEsp32StatusPanel';
import { useMissionSocket } from './hooks/useMissionSocket';
import type { LatLng, Payload } from './types';

const DEFAULT_CENTER: LatLng = { lat: 13.0827, lng: 80.2707 };

export default function App() {
  const [boundaryPoints, setBoundaryPoints] = useState<LatLng[]>([]);
  const [fieldLocked, setFieldLocked] = useState(false);
  const [payload, setPayload] = useState<Payload>('IRRIGATION');
  const [soilType, setSoilType] = useState('loam');
  const [dose, setDose] = useState('0');
  const [spacing, setSpacing] = useState('0');
  const [rowSpacing, setRowSpacing] = useState('1.0');
  const [samplingSpacing, setSamplingSpacing] = useState('3.0');
  const [localError, setLocalError] = useState<string | null>(null);

  const {
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
  } = useMissionSocket();

  const resources = telemetry?.resources_used ?? null;

  const mapCenter = useMemo(
    () => boundaryPoints[0] ?? DEFAULT_CENTER,
    [boundaryPoints]
  );

  const missionState =
    telemetry?.rover_status ??
    (missionPlan
      ? missionPaused
        ? 'MISSION PAUSED'
        : 'MISSION READY'
      : fieldLocked
        ? 'SUBMITTING'
        : 'FIELD SETUP');

  const displayedRowSpacing =
    missionPlan?.row_spacing_m ?? (Number(rowSpacing) || 1.0);

  const displayedSamplingSpacing =
    missionPlan?.sampling_density_m ??
    (Number(samplingSpacing) || 3.0);

  useEffect(() => {
    if (error && fieldLocked && !missionPlan) {
      setFieldLocked(false);
    }
  }, [error, fieldLocked, missionPlan]);

  const handleMapClick = (event: LeafletMouseEvent) => {
    if (fieldLocked) return;

    setBoundaryPoints((points) => [
      ...points,
      {
        lat: event.latlng.lat,
        lng: event.latlng.lng,
      },
    ]);

    setLocalError(null);
  };

  const handleStart = () => {
    if (!connected) {
      setLocalError(
        'Backend is offline. Connect the backend before starting a mission.'
      );
      return;
    }

    if (boundaryPoints.length < 3) {
      setLocalError(
        'Select at least three boundary points before starting.'
      );
      return;
    }

    const doseValue = Number(dose);
    const spacingValue = Number(spacing);
    const requestedRowSpacing = Number(rowSpacing);
    const requestedSamplingSpacing = Number(samplingSpacing);

    if (!Number.isFinite(doseValue) || !Number.isFinite(spacingValue)) {
      setLocalError('Prescription values must be valid numbers.');
      return;
    }

    if (
      !Number.isFinite(requestedRowSpacing) ||
      requestedRowSpacing <= 0 ||
      !Number.isFinite(requestedSamplingSpacing) ||
      requestedSamplingSpacing <= 0
    ) {
      setLocalError(
        'Row spacing and sampling spacing must both be greater than zero.'
      );
      return;
    }

    setFieldLocked(true);

    const sent = startMission(
      boundaryPoints,
      payload,
      {
        dose_grams: doseValue || 0,
        spacing_m: spacingValue || 0,
      },
      soilType,
      requestedRowSpacing,
      requestedSamplingSpacing
    );

    if (!sent) {
      setFieldLocked(false);
    }
  };

  const reset = () => {
    stopMission();
    resetMission();
    setBoundaryPoints([]);
    setFieldLocked(false);
    setLocalError(null);
  };

  const handlePauseResume = () => {
    if (missionPaused) {
      resumeMission();
    } else {
      pauseMission();
    }
  };

  const visibleError = localError ?? error;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-glyph">AR</div>

          <div>
            <strong>AgriRover</strong>
            <span>Precision field operations</span>
          </div>
        </div>

        <div className="topbar-right">
          <span className="session-label">CONTROL ROOM / 01</span>
          <ConnectionBadge connected={connected} />
        </div>
      </header>

      <main className="dashboard">
        <section className="intro">
          <div>
            <span className="eyebrow">Autonomous mission control</span>

            <h1>
              Field operations, <em>in view.</em>
            </h1>

            <p>
              Define a boundary, dispatch the rover, and monitor every pass
              from one calm workspace.
            </p>
          </div>

          <div className="mission-state">
            <span className="state-kicker">Current state</span>
            <strong>{missionState}</strong>
            <span className="state-line" />
          </div>
        </section>

        {visibleError && (
          <div className="alert" role="alert">
            <span className="alert-icon">!</span>

            <span>{visibleError}</span>

            <button
              onClick={() => setLocalError(null)}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        <section className="workspace">
          <div className="map-column">
            <div className="map-frame">
              <div className="map-toolbar">
                <div>
                  <span className="eyebrow">Field canvas</span>

                  <strong>
                    {boundaryPoints.length
                      ? `${boundaryPoints.length} boundary points`
                      : 'Click to define your field'}
                  </strong>
                </div>

                <span className="map-legend">
                  <i className="legend-field" /> boundary{' '}
                  <i className="legend-route" /> planned route{' '}
                  <i className="legend-rover" /> actual route
                </span>
              </div>

              <MapPanel
                boundaryPoints={boundaryPoints}
                missionPlan={missionPlan}
                telemetry={telemetry}
                telemetryHistory={telemetryHistory}
                activePayload={payload}
                onMapClick={handleMapClick}
                center={mapCenter}
              />

              <div className="map-footer">
                <span>Rows: {displayedRowSpacing} m</span>
                <span>Sampling: {displayedSamplingSpacing} m</span>
                <span>Coverage generated by backend</span>
              </div>
            </div>

            <div className="control-bar">
              <div className="control-fields">
                <label>
                  Active payload
                  <select
                    value={payload}
                    onChange={(event) =>
                      setPayload(event.target.value as Payload)
                    }
                    disabled={fieldLocked}
                  >
                    <option>MAPPING</option>
                    <option>IRRIGATION</option>
                    <option>SEEDING</option>
                    <option>FERTILIZER</option>
                  </select>
                </label>

                <label>
                  Soil type
                  <select
                    value={soilType}
                    onChange={(event) => setSoilType(event.target.value)}
                    disabled={fieldLocked}
                  >
                    <option>loam</option>
                    <option>sandy</option>
                    <option>clay</option>
                    <option>silt</option>
                    <option>red_soil</option>
                  </select>
                </label>

                <label>
                  Row spacing
                  <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={rowSpacing}
                    onChange={(event) => setRowSpacing(event.target.value)}
                    disabled={fieldLocked}
                  />
                  <small>meters</small>
                </label>

                <label>
                  Sampling spacing
                  <input
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={samplingSpacing}
                    onChange={(event) =>
                      setSamplingSpacing(event.target.value)
                    }
                    disabled={fieldLocked}
                  />
                  <small>meters</small>
                </label>

                <label>
                  Prescription dose
                  <input
                    type="number"
                    min="0"
                    value={dose}
                    onChange={(event) => setDose(event.target.value)}
                    disabled={fieldLocked}
                  />
                  <small>grams</small>
                </label>

                <label>
                  Payload spacing
                  <input
                    type="number"
                    min="0"
                    value={spacing}
                    onChange={(event) => setSpacing(event.target.value)}
                    disabled={fieldLocked}
                  />
                  <small>meters</small>
                </label>
              </div>

              <div className="control-actions">
                <button
                  className="button ghost"
                  onClick={reset}
                  disabled={missionPaused}
                >
                  Reset field
                </button>

                {fieldLocked && (
                  <button
                    className={`button ${missionPaused
                        ? 'button-resume'
                        : 'button-pause'
                      }`}
                    onClick={handlePauseResume}
                    aria-label={
                      missionPaused
                        ? 'Resume mission'
                        : 'Stop mission'
                    }
                  >
                    {missionPaused ? 'Resume' : 'Stop'}
                  </button>
                )}

                <button
                  className="button primary"
                  onClick={handleStart}
                  disabled={fieldLocked}
                >
                  {fieldLocked ? 'Mission active' : 'Start mission'}
                  <span>→</span>
                </button>
              </div>
            </div>

            <TemporaryEsp32StatusPanel telemetry={telemetry} />
          </div>

          <aside className="side-column">
            <MissionPanel plan={missionPlan} />
            <TelemetryPanel telemetry={telemetry} />
            <ResourcesPanel resources={resources} />
          </aside>
        </section>

        <section className="insight-grid">
          <div className="panel">
            <div className="panel-heading">
              <span className="eyebrow">Sensor trend</span>
              <span className="panel-mark">
                {telemetryHistory.length} samples
              </span>
            </div>

            <div className="sparkline">
              {telemetryHistory.length ? (
                telemetryHistory.slice(-24).map((sample, index) => (
                  <i
                    key={`${sample.timestamp}-${index}`}
                    style={{
                      height: `${Math.max(
                        8,
                        sample.soil_moisture_pct ?? 8
                      )}%`,
                    }}
                  />
                ))
              ) : (
                <span className="empty-state">
                  Waiting for telemetry
                </span>
              )}
            </div>

            <div className="data-row">
              <span>Soil moisture</span>

              <strong>
                {telemetry?.soil_moisture_pct === null ||
                  telemetry?.soil_moisture_pct === undefined
                  ? 'No sample yet'
                  : `${telemetry.soil_moisture_pct.toFixed(1)}%`}
              </strong>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <span className="eyebrow">AI soil estimates</span>
              <span className="source-badge model">ML_MODEL</span>
            </div>

            {predictions.length ? (
              <div className="data-list">
                {predictions.slice(-4).map((prediction) => (
                  <div
                    className="data-row"
                    key={`${prediction.timestamp}-${prediction.x_m}-${prediction.y_m}`}
                  >
                    <span>
                      {prediction.x_m.toFixed(1)}m /{' '}
                      {prediction.y_m.toFixed(1)}m
                    </span>

                    <strong>
                      {prediction.predicted_moisture_pct.toFixed(1)}%
                    </strong>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <strong>No estimates yet</strong>

                <span>
                  Model predictions will appear for unsampled points when
                  broadcast by the backend.
                </span>
              </div>
            )}
          </div>
        </section>
      </main>

      <footer>
        <span>AGR • AUTONOMOUS GROUND ROBOTICS</span>
        <span>
          System telemetry is advisory. Hardware safety controls remain local.
        </span>
      </footer>
    </div>
  );
}