import type { TelemetryData } from '../types';

const display = (value: number | undefined, suffix = '') => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)}${suffix}` : '--';

export function TelemetryPanel({ telemetry }: { telemetry: TelemetryData | null }) {
  return <section className="panel telemetry-panel">
    <div className="panel-heading"><span className="eyebrow">Live telemetry</span><span className={`telemetry-dot ${telemetry ? 'active' : ''}`} /></div>
    {telemetry ? <>
      <div className="rover-readout"><div><span className="readout-label">Rover state</span><strong>{telemetry.rover_status || 'UNKNOWN'}</strong></div><div className="battery"><span>Battery</span><strong>{display(telemetry.battery_pct, '%')}</strong></div></div>
      <div className="data-list"><Data label="Position" value={`${display(telemetry.current_x_m)}m / ${display(telemetry.current_y_m)}m`} /><Data label="Heading" value={display(telemetry.heading_deg, '°')} /><Data label="GPS" value={`${display(telemetry.gps_lat, '°')}, ${display(telemetry.gps_lng, '°')}`} /><Data label="Soil moisture" value={display(telemetry.soil_moisture_pct, '%')} /><Data label="Payload" value={telemetry.active_payload || '--'} /></div>
    </> : <div className="empty-state"><strong>Waiting for rover signal</strong><span>Telemetry will appear here once the backend receives a packet.</span></div>}
  </section>;
}
function Data({ label, value }: { label: string; value: string }) { return <div className="data-row"><span>{label}</span><strong>{value}</strong></div>; }
