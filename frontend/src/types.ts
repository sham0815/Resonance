export interface LatLng { lat: number; lng: number }

export interface MissionPlan {
  field_id: string;
  row_spacing_m: number;
  sampling_density_m: number;
  hull_area_m2: number;
  grid_orientation_deg: number;
  waypoints_local: [number, number][];
  waypoints_gps: LatLng[];
  sampling_points: [number, number][];
  total_distance_m: number;
  estimated_time_min: number;
}

export interface ResourcesUsed {
  fertilizer_g: number;
  water_ml: number;
  seeds: number;
}

export type RoverStatus = 'IDLE' | 'NAVIGATING' | 'ARRIVED_AT_NODE' | 'PERFORMING_ACTION' | 'COMM_LOST' | 'LOW_BATTERY' | 'STUCK' | 'MISSION_COMPLETE' | string;

export interface TelemetryData {
  timestamp: number;
  rover_status: RoverStatus;
  current_x_m: number;
  current_y_m: number;
  heading_deg: number;
  gps_lat: number;
  gps_lng: number;
  soil_moisture_pct: number;
  battery_pct: number;
  active_payload: string;
  resources_used: ResourcesUsed;
}

export type BackendMessage =
  | { type: 'MISSION_STARTED'; plan: MissionPlan }
  | { type: 'MISSION_ERROR'; error: string }
  | { type: 'TELEMETRY'; payload: TelemetryData };
