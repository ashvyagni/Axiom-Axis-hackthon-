from axiom.tools.implementations.core_tools import haversine


def test_haversine_same_point():
    assert haversine(40.7128, -74.006, 40.7128, -74.006) == 0.0


def test_haversine_known_distance():
    dist = haversine(40.7128, -74.006, 40.7158, -74.002)
    assert 0.3 < dist < 0.6


def test_haversine_further_distance():
    dist = haversine(40.7128, -74.006, 40.7580, -73.9855)
    assert 4.0 < dist < 6.0
