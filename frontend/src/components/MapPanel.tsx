import type { LeafletMouseEvent } from 'leaflet';
import { Circle, CircleMarker, MapContainer, Polygon, Polyline, TileLayer, Tooltip, useMapEvents } from 'react-leaflet';
import type { LatLng, MissionPlan, TelemetryData } from '../types';

interface Props { boundaryPoints: LatLng[]; missionPlan: MissionPlan | null; telemetry: TelemetryData | null; onMapClick: (event: LeafletMouseEvent) => void; center: LatLng }

function MapClickHandler({ onMapClick }: Pick<Props, 'onMapClick'>) {
  useMapEvents({ click: onMapClick });
  return null;
}

export default function MapPanel({ boundaryPoints, missionPlan, telemetry, onMapClick, center }: Props) {
  const rover = telemetry && Number.isFinite(telemetry.gps_lat) && Number.isFinite(telemetry.gps_lng)
    ? [telemetry.gps_lat, telemetry.gps_lng] as [number, number] : null;
  const route = missionPlan?.waypoints_gps ?? [];
  return (
    <MapContainer className="map-canvas" center={[center.lat, center.lng]} zoom={17}>
      <MapClickHandler onMapClick={onMapClick} />
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {boundaryPoints.length > 1 && <Polygon positions={boundaryPoints.map((point) => [point.lat, point.lng])} pathOptions={{ fillColor: '#8ed6a8', fillOpacity: 0.2, color: '#2c8b5c', weight: 2 }} />}
      {route.length > 1 && <Polyline positions={route.map((point) => [point.lat, point.lng])} pathOptions={{ color: '#e35f3d', opacity: 0.95, weight: 4 }} />}
      {boundaryPoints.map((point, index) => <CircleMarker key={`boundary-${index}`} center={[point.lat, point.lng]} radius={8} pathOptions={{ fillColor: '#2c8b5c', fillOpacity: 1, color: '#ffffff', weight: 2 }}><Tooltip permanent direction="center">{index + 1}</Tooltip></CircleMarker>)}
      {route.map((point, index) => <Circle key={`waypoint-${index}`} center={[point.lat, point.lng]} radius={1.8} pathOptions={{ fillColor: '#ed714d', fillOpacity: 1, color: '#fffdf7', weight: 1 }} />)}
      {rover && <CircleMarker center={rover} radius={8} pathOptions={{ fillColor: '#176b58', fillOpacity: 1, color: '#ffffff', weight: 2 }}><Tooltip direction="top">Rover position</Tooltip></CircleMarker>}
    </MapContainer>
  );
}
