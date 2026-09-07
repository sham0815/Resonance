import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from path_planner import ConvexHullPlanner, CoordinateTransformer


def test_transformer_round_trip():
    """Test that GPS -> local -> GPS round trip is accurate."""
    t = CoordinateTransformer(13.0827, 80.2707)
    x, y = t.gps_to_local(13.0830, 80.2710)
    lat, lng = t.local_to_gps(x, y)
    assert abs(lat - 13.0830) < 1e-6
    assert abs(lng - 80.2710) < 1e-6


def test_rejects_too_few_points():
    """Test that fewer than 3 points are rejected."""
    with pytest.raises(ValueError, match="Minimum 3 boundary points required"):
        ConvexHullPlanner().generate_grid([{"lat": 0, "lng": 0}, {"lat": 0, "lng": 0.0001}])


def test_rejects_tiny_area():
    """Test that fields smaller than 4 m² are rejected."""
    pts = [
        {"lat": 13.0000, "lng": 80.0000},
        {"lat": 13.00001, "lng": 80.0000},
        {"lat": 13.00001, "lng": 80.00001},
    ]
    with pytest.raises(ValueError, match="4 m²"):
        ConvexHullPlanner().generate_grid(pts)


def test_generates_waypoints_for_square_field():
    """Test that a valid ~10x10m field generates waypoints."""
    # Use a real ~10x10m square in degrees (Chennai area)
    # ~9m per degree at this latitude
    pts = [
        {"lat": 13.08000, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27010},
        {"lat": 13.08000, "lng": 80.27010},
    ]
    plan = ConvexHullPlanner(row_spacing_m=1.0).generate_grid(pts)

    # Check that result has all required fields
    assert "hull_area_m2" in plan
    assert "waypoints_local" in plan
    assert "waypoints_gps" in plan
    assert "sampling_points" in plan
    assert "total_distance_m" in plan
    assert "estimated_time_min" in plan

    # Check values make sense
    assert plan["hull_area_m2"] > 4.0  # At least 4 m²
    assert len(plan["waypoints_local"]) > 0
    assert len(plan["waypoints_gps"]) == len(plan["waypoints_local"])
    assert plan["total_distance_m"] > 0
    assert plan["estimated_time_min"] > 0
    assert plan["estimated_time_min"] == pytest.approx(plan["total_distance_m"] / 30.0)


def test_waypoint_gps_local_correspondence():
    """Test that GPS and local waypoints correspond correctly."""
    pts = [
        {"lat": 13.08000, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27000},
        {"lat": 13.08010, "lng": 80.27010},
        {"lat": 13.08000, "lng": 80.27010},
    ]
    plan = ConvexHullPlanner(row_spacing_m=1.0).generate_grid(pts)

    transformer = CoordinateTransformer(pts[0]["lat"], pts[0]["lng"])

    # Pick the first waypoint and verify conversion
    local_wp = plan["waypoints_local"][0]
    gps_wp = plan["waypoints_gps"][0]

    # Convert local back to GPS and compare
    lat, lng = transformer.local_to_gps(local_wp[0], local_wp[1])
    assert abs(lat - gps_wp["lat"]) < 1e-6
    assert abs(lng - gps_wp["lng"]) < 1e-6


def test_rotated_field_has_sensible_grid_orientation():
    """Regression test for Shapely's radians-versus-degrees rotation API."""
    transformer = CoordinateTransformer(13.08, 80.27)
    local = [(0, 0), (10.3923, 6), (7.3923, 11.1962), (-3, 5.1962)]
    pts = [{"lat": transformer.local_to_gps(x, y)[0], "lng": transformer.local_to_gps(x, y)[1]} for x, y in local]
    plan = ConvexHullPlanner(row_spacing_m=1.0).generate_grid(pts)
    orientation = plan["grid_orientation_deg"] % 180
    assert orientation == pytest.approx(30, abs=1)
    assert len(plan["waypoints_local"]) >= 10


def test_rejects_non_positive_spacing():
    with pytest.raises(ValueError, match="row_spacing_m"):
        ConvexHullPlanner(row_spacing_m=0)
