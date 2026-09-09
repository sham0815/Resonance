export interface LatLng { lat: number; lng: number }

export interface MissionPlan {
  field_id?: string;
  row_spacing_m?: number;
  sampling_density_m?: number;
  hull_area_m2: number;
  grid_orientation_deg: number;
  waypoints_local: [number, number][];
  waypoints_gps: LatLng[];
  sampling_points: [number, number][];
  total_distance_m: number;
  estimated_time_min: number;
}

export interface ResourcesUsed {
  fertilizer_g: number | null;
  water_ml: number | null;
  seeds: number | null;
}

export type TelemetrySource = 'SENSOR' | 'SIMULATION';
export type RoverStatus = 'IDLE' | 'READY' | 'NAVIGATING' | 'ARRIVED_AT_NODE' | 'PERFORMING_ACTION' | 'SOWING' | 'WATERING' | 'FERTILIZING' | 'PAUSED' | 'STOPPED' | 'EMERGENCY STOP' | 'COMMUNICATION LOST' | 'LOW BATTERY' | 'STUCK' | 'MISSION COMPLETE' | string;
export type Payload = 'MAPPING' | 'SEEDING' | 'FERTILIZER' | 'IRRIGATION';

export interface TelemetryData {
  timestamp: number;
  source?: TelemetrySource;
  x_m: number | null;
  y_m: number | null;
  current_x_m?: number | null;
  current_y_m?: number | null;
  soil_moisture_pct: number | null;
  humidity_pct?: number | null;
  depth_mm?: number | null;
  rover_status: RoverStatus | null;
  gps_lat: number | null;
  gps_lng: number | null;
  heading_deg: number | null;
  battery_pct: number | null;
  active_payload: Payload | string | null;
  resources_used: ResourcesUsed | null;

  // TEMPORARY ESP32 sensor/status bridge. Optional to preserve existing contract.
  soil_moisture_raw?: number;
  obstacle_distance_cm?: number | null;
  ambient_temperature_c?: number;
  relative_humidity_pct?: number;
  movement_status?: 'MOVING_FORWARD' | 'STOPPED' | string;
  pump_status?: 'ON' | 'OFF' | string;
  operational_phase?: 'NAVIGATION_MONITORING' | 'IRRIGATION_WATERING' | string;
}

export interface SoilMoisturePrediction {
  field_id: string;
  x_m: number;
  y_m: number;
  depth_mm: number;
  soil_type: string;
  humidity_pct: number | null;
  hours_since_irrigation: number | null;
  timestamp: number;
  model_name: string;
  version: string;
  predicted_moisture_pct: number;
  source: 'ML_MODEL';
}

export type BackendMessage =
  | { type: 'MISSION_STARTED'; plan: MissionPlan }
  | { type: 'MISSION_ERROR'; error: string }
  | { type: 'MISSION_STOPPED'; message: string }
  | { type: 'MISSION_PAUSED' }
  | { type: 'MISSION_RESUMED' }
  | { type: 'TELEMETRY'; payload: TelemetryData }
  | { type: 'AI_SOIL_MOISTURE_PREDICTION'; payload: SoilMoisturePrediction };
