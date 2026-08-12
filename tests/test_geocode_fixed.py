from velox.geocode_fixed import point_at_km


def _straight_line_east(n=101):
    # ~1.1 km spacing per 0.01 degrees of longitude at this latitude.
    return [[9.0 + i * 0.01, 45.0] for i in range(n)]


def test_point_at_zero_km_is_the_start():
    assert point_at_km(_straight_line_east(), 0.0) == [9.0, 45.0]


def test_point_at_km_interpolates_along_the_line():
    geometry = _straight_line_east()
    point = point_at_km(geometry, 10.0)
    assert point is not None
    assert 9.0 < point[0] < 9.2
    assert abs(point[1] - 45.0) < 1e-9


def test_km_beyond_the_line_returns_none_rather_than_the_end():
    assert point_at_km(_straight_line_east(), 10_000.0) is None


def test_empty_geometry_returns_none():
    assert point_at_km([], 5.0) is None
    assert point_at_km([[9.0, 45.0]], 5.0) is None
