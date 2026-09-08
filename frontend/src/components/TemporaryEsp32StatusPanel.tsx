import type { TelemetryData } from '../types';

// TEMPORARY: Delete this file and its App.tsx usage when the prototype ESP32
// telemetry fields are replaced by the final rover telemetry contract.
const number = (value: number | undefined, suffix: string) =>
  typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)}${suffix}` : 'NULL';

const text = (value: string | undefined) => value || 'NULL';

export function TemporaryEsp32StatusPanel({ telemetry }: { telemetry: TelemetryData | null }) {
  const distance = telemetry?.obstacle_distance_cm;
  const distanceValue = typeof distance !== 'number' || !Number.isFinite(distance)
    ? 'NULL' : distance >= 999 ? 'No object' : `${distance.toFixed(1)} cm`;

  return <section className="panel esp32-status-panel" aria-label="Temporary ESP32 status">
    <div className="panel-heading"><span className="eyebrow">ESP32 live bridge</span><span className={`mini-state ${telemetry ? 'live' : ''}`}>{telemetry ? 'SIGNAL RECEIVED' : 'WAITING FOR SIGNAL'}</span></div>
    <div className="esp32-section"><span className="esp32-section-title">Environmental &amp; soil</span><div className="esp32-grid">
      <Data label="Moisture raw" value={number(telemetry?.soil_moisture_raw, '')} />
      <Data label="Obstacle" value={distanceValue} />
      <Data label="Temperature" value={number(telemetry?.ambient_temperature_c, ' °C')} />
      <Data label="Humidity" value={number(telemetry?.relative_humidity_pct, '%')} />
    </div></div>
    <div className="esp32-section"><span className="esp32-section-title">System state</span><div className="esp32-state-list">
      <Data label="Movement" value={text(telemetry?.movement_status)} />
      <Data label="Water pump" value={text(telemetry?.pump_status)} />
      <Data label="Phase" value={text(telemetry?.operational_phase)} />
    </div></div>
  </section>;
}

function Data({ label, value }: { label: string; value: string }) {
  return <div className="esp32-data"><span>{label}</span><strong>{value}</strong></div>;
}
