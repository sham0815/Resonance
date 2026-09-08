"""Deterministic GPS-to-Boustrophedon mission planning for AgriRover."""

import math
from typing import Any, Dict, List, Sequence, Tuple

from shapely.affinity import rotate
from shapely.geometry import LineString, MultiPoint, Polygon


LocalPoint = Tuple[float, float]


class CoordinateTransformer:
    """Convert small-area GPS coordinates to/from a local east/north frame."""

    R = 6_371_000.0

    def __init__(self, home_lat: float, home_lng: float):
        self.home_lat = float(home_lat)
        self.home_lng = float(home_lng)
        if not -90.0 <= self.home_lat <= 90.0 or not -180.0 <= self.home_lng <= 180.0:
            raise ValueError("Home coordinate is outside valid latitude/longitude bounds")

    def gps_to_local(self, lat: float, lng: float) -> LocalPoint:
        lat, lng = float(lat), float(lng)
        if not -90.0 <= lat <= 90.0 or not -180.0 <= lng <= 180.0:
            raise ValueError("Boundary point is outside valid latitude/longitude bounds")
        home_lat_rad = math.radians(self.home_lat)
        return (
            math.radians(lng - self.home_lng) * self.R * math.cos(home_lat_rad),
            math.radians(lat - self.home_lat) * self.R,
        )

    def local_to_gps(self, x: float, y: float) -> LocalPoint:
        lat = self.home_lat + math.degrees(float(y) / self.R)
        lng = self.home_lng + math.degrees(float(x) / (self.R * math.cos(math.radians(self.home_lat))))
        return lat, lng


class ConvexHullPlanner:
    """Generate a lawnmower route for the convex hull of a clicked boundary."""

    MIN_FIELD_AREA_M2 = 4.0

    def __init__(self, row_spacing_m: float = 1.0, sampling_density_m: float = 3.0):
        self.row_spacing = self._positive_number(row_spacing_m, "row_spacing_m")
        self.sampling_density = self._positive_number(sampling_density_m, "sampling_density_m")

    @staticmethod
    def _positive_number(value: float, name: str) -> float:
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive number") from exc
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive number")
        return value

    def generate_grid(self, user_points: Sequence[Dict[str, float]], field_id: str = "field_alpha") -> Dict[str, Any]:
        if len(user_points) < 3:
            raise ValueError("Minimum 3 boundary points required")
        try:
            transformer = CoordinateTransformer(user_points[0]["lat"], user_points[0]["lng"])
            local_points = [transformer.gps_to_local(point["lat"], point["lng"]) for point in user_points]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Each boundary point must contain valid lat and lng values") from exc

        hull = MultiPoint(local_points).convex_hull
        if not isinstance(hull, Polygon) or hull.is_empty:
            raise ValueError("Points do not form a valid polygon (collinear or duplicate points)")
        if hull.area < self.MIN_FIELD_AREA_M2:
            raise ValueError(f"Field area {hull.area:.2f} m² is below the {self.MIN_FIELD_AREA_M2:.0f} m² minimum")

        grid_angle = self._minimum_bounding_rectangle(hull)["orientation"]
        # Shapely angles are explicitly radians; this prevents the historic degrees/radians bug.
        rotated_hull = rotate(hull, -grid_angle, origin=(0, 0), use_radians=True)
        rotated_path = self._generate_axis_aligned_grid(rotated_hull)
        if len(rotated_path) < 2:
            raise ValueError("Field does not produce a navigable coverage path")

        waypoints_local = [self._rotate_point(point, grid_angle, (0, 0)) for point in rotated_path]
        sampling_points = self._insert_sampling_points(waypoints_local, self.sampling_density)
        waypoints_gps = [transformer.local_to_gps(*point) for point in waypoints_local]
        total_distance = self._path_length(waypoints_local)
        return {
            "field_id": field_id,
            "row_spacing_m": self.row_spacing,
            "sampling_density_m": self.sampling_density,
            "hull_area_m2": float(hull.area),
            "grid_orientation_deg": math.degrees(grid_angle),
            "waypoints_local": [[float(x), float(y)] for x, y in waypoints_local],
            "waypoints_gps": [{"lat": float(lat), "lng": float(lng)} for lat, lng in waypoints_gps],
            "sampling_points": [[float(x), float(y)] for x, y in sampling_points],
            "total_distance_m": float(total_distance),
            "estimated_time_min": float(total_distance / (0.5 * 60.0)),
        }

    @staticmethod
    def _minimum_bounding_rectangle(polygon: Polygon) -> Dict[str, float]:
        coords = list(polygon.exterior.coords)[:-1]
        best: Dict[str, float] = {"orientation": 0.0, "area": math.inf}
        for index, start in enumerate(coords):
            end = coords[(index + 1) % len(coords)]
            angle = math.atan2(end[1] - start[1], end[0] - start[0])
            rotated = rotate(polygon, -angle, origin=(0, 0), use_radians=True)
            minx, miny, maxx, maxy = rotated.bounds
            area = (maxx - minx) * (maxy - miny)
            if area < best["area"] - 1e-9:
                best = {"orientation": angle, "area": area}
        return best

    def _generate_axis_aligned_grid(self, polygon: Polygon) -> List[LocalPoint]:
        minx, miny, maxx, maxy = polygon.bounds
        path: List[LocalPoint] = []
        row_index = 0
        y = miny + min(self.row_spacing / 2.0, (maxy - miny) / 2.0)
        while y < maxy - 1e-9:
            clipped = LineString([(minx - 1.0, y), (maxx + 1.0, y)]).intersection(polygon)
            if clipped.geom_type == "LineString":
                segments = [clipped]
            elif clipped.geom_type == "MultiLineString":
                segments = list(clipped.geoms)
            else:
                segments = []
            for segment in sorted(segments, key=lambda item: item.bounds[0]):
                coords = list(segment.coords)
                if len(coords) >= 2 and segment.length > 1e-9:
                    endpoints = [(float(coords[0][0]), y), (float(coords[-1][0]), y)]
                    path.extend(endpoints if row_index % 2 == 0 else reversed(endpoints))
                    row_index += 1
            y += self.row_spacing
        return path

    @staticmethod
    def _insert_sampling_points(path: Sequence[LocalPoint], density_m: float) -> List[LocalPoint]:
        if len(path) < 2:
            return []
        samples: List[LocalPoint] = []
        distance_to_sample = density_m
        for start, end in zip(path, path[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            while length + 1e-9 >= distance_to_sample:
                ratio = distance_to_sample / length
                sample = (start[0] + ratio * dx, start[1] + ratio * dy)
                samples.append(sample)
                start, length, distance_to_sample = sample, length - distance_to_sample, density_m
                dx, dy = end[0] - start[0], end[1] - start[1]
            distance_to_sample -= length
        return samples

    @staticmethod
    def _path_length(path: Sequence[LocalPoint]) -> float:
        return sum(math.dist(start, end) for start, end in zip(path, path[1:]))

    @staticmethod
    def _rotate_point(point: LocalPoint, angle: float, origin: LocalPoint) -> LocalPoint:
        x, y = point[0] - origin[0], point[1] - origin[1]
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        return cos_angle * x - sin_angle * y + origin[0], sin_angle * x + cos_angle * y + origin[1]
