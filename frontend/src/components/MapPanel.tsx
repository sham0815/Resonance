import { Circle, GoogleMap, Marker, Polygon, Polyline } from '@react-google-maps/api';
import type { LatLng, MissionPlan, TelemetryData } from '../types';

const mapStyle = [{ featureType: 'poi', stylers: [{ visibility: 'off' }] }];
const options = { disableDefaultUI: true, zoomControl: true, styles: mapStyle };

interface Props { boundaryPoints: LatLng[]; missionPlan: MissionPlan | null; telemetry: TelemetryData | null; onMapClick: (event: google.maps.MapMouseEvent) => void; center: LatLng }

export default function MapPanel({ boundaryPoints, missionPlan, telemetry, onMapClick, center }: Props) {
  const rover = telemetry && Number.isFinite(telemetry.gps_lat) && Number.isFinite(telemetry.gps_lng)
    ? { lat: telemetry.gps_lat, lng: telemetry.gps_lng } : null;
  const route = missionPlan?.waypoints_gps ?? [];
  return (
    <GoogleMap mapContainerClassName="map-canvas" center={center} zoom={17} options={options} onClick={onMapClick}>
      {boundaryPoints.length > 1 && <Polygon path={boundaryPoints} options={{ fillColor: '#8ed6a8', fillOpacity: 0.2, strokeColor: '#2c8b5c', strokeWeight: 2, clickable: false }} />}
      {route.length > 1 && <Polyline path={route} options={{ strokeColor: '#e35f3d', strokeOpacity: 0.95, strokeWeight: 4, clickable: false }} />}
      {boundaryPoints.map((point, index) => <Marker key={`boundary-${index}`} position={point} label={{ text: String(index + 1), color: '#ffffff', fontWeight: '700' }} />)}
      {route.map((point, index) => <Circle key={`waypoint-${index}`} center={point} radius={1.8} options={{ fillColor: '#ed714d', fillOpacity: 1, strokeColor: '#fffdf7', strokeWeight: 1 }} />)}
      {rover && <Marker position={rover} title="Rover position" icon={{ path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW, scale: 6, fillColor: '#176b58', fillOpacity: 1, strokeColor: '#ffffff', strokeWeight: 2, rotation: telemetry?.heading_deg ?? 0 }} />}
    </GoogleMap>
  );
}
