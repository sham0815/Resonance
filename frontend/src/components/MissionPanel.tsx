import type { MissionPlan } from '../types';

const format = (value: number, digits = 1) => Number.isFinite(value) ? value.toFixed(digits) : '--';

export function MissionPanel({ plan }: { plan: MissionPlan | null }) {
  return <section className="panel mission-panel">
    <div className="panel-heading"><span className="eyebrow">Mission output</span><span className={`mini-state ${plan ? 'live' : ''}`}>{plan ? 'PLANNED' : 'AWAITING FIELD'}</span></div>
    {plan ? <div className="metric-grid">
      <Metric label="Field area" value={`${format(plan.hull_area_m2)} m²`} />
      <Metric label="Coverage route" value={`${format(plan.total_distance_m)} m`} />
      <Metric label="Est. duration" value={`${format(plan.estimated_time_min)} min`} />
      <Metric label="Grid heading" value={`${format(plan.grid_orientation_deg)}°`} />
      <Metric label="Row spacing" value={`${format(plan.row_spacing_m)} m`} />
      <Metric label="Sampling spacing" value={`${format(plan.sampling_density_m)} m`} />
      <Metric label="Waypoints" value={String(plan.waypoints_gps?.length ?? 0)} />
      <Metric label="Sampling points" value={String(plan.sampling_points?.length ?? 0)} />
    </div> : <div className="empty-state"><strong>No mission plan yet</strong><span>Click at least three points on the map to define a field.</span></div>}
  </section>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div>; }
