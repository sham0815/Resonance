import type { ResourcesUsed } from '../types';

export function ResourcesPanel({ resources }: { resources: ResourcesUsed }) {
  return <section className="panel resources-panel"><div className="panel-heading"><span className="eyebrow">Resources used</span><span className="panel-mark">▦</span></div><div className="resource-list"><Resource label="Water" value={resources.water_ml} suffix="ml" /><Resource label="Fertilizer" value={resources.fertilizer_g} suffix="g" /><Resource label="Seeds" value={resources.seeds} suffix="units" /></div></section>;
}
function Resource({ label, value, suffix }: { label: string; value: number; suffix: string }) { return <div className="resource"><span>{label}</span><strong>{Number.isFinite(value) ? value : 0}<small>{suffix}</small></strong></div>; }
