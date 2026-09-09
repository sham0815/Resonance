import type { LeafletMouseEvent } from 'leaflet';
import { Circle, CircleMarker, MapContainer, Polygon, Polyline, TileLayer, Tooltip, useMapEvents } from 'react-leaflet';
import type { LatLng, MissionPlan, Payload, TelemetryData } from '../types';

// Payload-based colour palette — border only, no fill
const PAYLOAD_COLORS: Record<string, { border: string; route: string; dot: string; label: string }> = {
  IRRIGATION: { border: '#2563eb', route: '#3b82f6', dot: '#93c5fd', label: 'Irrigation' },
  SEEDING:    { border: '#16a34a', route: '#22c55e', dot: '#86efac', label: 'Seeding' },
  FERTILIZER: { border: '#d97706', route: '#f59e0b', dot: '#fcd34d', label: 'Fertilizer' },
  MAPPING:    { border: '#7c3aed', route: '#a855f7', dot: '#d8b4fe', label: 'Mapping' },
};
const DEFAULT_COLORS = { border: '#2c8b5c', route: '#e35f3d', dot: '#ed714d', label: 'Field' };

interface Props {
  boundaryPoints: LatLng[];
  missionPlan: MissionPlan | null;
  telemetry: TelemetryData | null;
  telemetryHistory?: TelemetryData[];
  activePayload?: Payload | string;
  onMapClick: (event: LeafletMouseEvent) => void;
  center: LatLng;
}

function MapClickHandler({ onMapClick }: Pick<Props, 'onMapClick'>) { useMapEvents({ click: onMapClick }); return null; }

export default function MapPanel({ boundaryPoints, missionPlan, telemetry, telemetryHistory = [], activePayload, onMapClick, center }: Props) {
  const colors = (activePayload && PAYLOAD_COLORS[activePayload]) ?? DEFAULT_COLORS;
  const rover = telemetry && telemetry.gps_lat !== null && telemetry.gps_lng !== null && Number.isFinite(telemetry.gps_lat) && Number.isFinite(telemetry.gps_lng) ? [telemetry.gps_lat, telemetry.gps_lng] as [number, number] : null;
  const route = missionPlan?.waypoints_gps ?? [];
  const actualRoute = telemetryHistory.filter((sample) => sample.gps_lat !== null && sample.gps_lng !== null && (sample.gps_lat !== 0 || sample.gps_lng !== 0)).map((sample) => [sample.gps_lat as number, sample.gps_lng as number] as [number, number]);
  return <MapContainer className="map-canvas" center={[center.lat, center.lng]} zoom={17}>
    <MapClickHandler onMapClick={onMapClick} />
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    {boundaryPoints.length > 1 && <Polygon positions={boundaryPoints.map((point) => [point.lat, point.lng])} pathOptions={{ fillOpacity: 0, color: colors.border, weight: 3 }} />}
    {route.length > 1 && <Polyline positions={route.map((point) => [point.lat, point.lng])} pathOptions={{ color: colors.route, opacity: 0.95, weight: 4 }} />}
    {actualRoute.length > 1 && <Polyline positions={actualRoute} pathOptions={{ color: '#176b58', opacity: 0.95, weight: 5 }} />}
    {boundaryPoints.map((point, index) => <CircleMarker key={`boundary-${index}`} center={[point.lat, point.lng]} radius={8} pathOptions={{ fillColor: colors.border, fillOpacity: 1, color: '#ffffff', weight: 2 }}><Tooltip permanent direction="center">{index + 1}</Tooltip></CircleMarker>)}
    {route.map((point, index) => <Circle key={`waypoint-${index}`} center={[point.lat, point.lng]} radius={1.8} pathOptions={{ fillColor: colors.dot, fillOpacity: 1, color: '#fffdf7', weight: 1 }} />)}
    {rover && <CircleMarker center={rover} radius={8} pathOptions={{ fillColor: '#176b58', fillOpacity: 1, color: '#ffffff', weight: 2 }}><Tooltip direction="top">Rover position</Tooltip></CircleMarker>}
  </MapContainer>;
}

export { PAYLOAD_COLORS, DEFAULT_COLORS };
