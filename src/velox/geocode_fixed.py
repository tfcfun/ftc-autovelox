"""Place a fixed camera from its road and kilometre.

Italian kilometre posts count from historical road origins, which do not always
coincide with the start of the OSM way. Interpolation is therefore marked
"medium" confidence and every point is reviewed by hand once (see review/index.html)
before being marked verified. A camera that cannot be placed keeps null
coordinates and is excluded from proximity alerts by the app.
"""

from __future__ import annotations

from pathlib import Path

from velox.overpass import _haversine_m, query_road_geometry
from velox.parse_fixed import FixedCamera


def point_at_km(geometry: list[list[float]], km: float) -> list[float] | None:
    if len(geometry) < 2 or km < 0:
        return None
    target_m = km * 1000.0
    travelled = 0.0
    for start, end in zip(geometry, geometry[1:]):
        span = _haversine_m(start, end)
        if travelled + span >= target_m:
            if span == 0:
                return list(start)
            ratio = (target_m - travelled) / span
            return [
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            ]
        travelled += span
    return None


def geocode(camera: FixedCamera, *, cache_dir: Path, ref_override: str | None = None) -> dict:
    """Place one camera.

    `ref_override` carries a road reference resolved from the PDF's descriptive
    denomination (see velox.road_names). The fixed-installation PDFs print
    "Milano - Napoli", never "A1", so without this every fixed camera would keep
    null coordinates and the precise layer of the map would be empty.
    """
    resolved_ref = camera.road_ref or ref_override
    identifier = "-".join(
        [
            "fx", camera.network[:4], (resolved_ref or camera.comune or "x"),
            camera.km_raw.replace("+", "").replace(",", ""),
            (camera.direction_raw or "na").lower(),
        ]
    )
    record = {
        "id": identifier,
        "network": camera.network,
        "region": camera.region,
        "road_name": camera.road_name,
        "road_ref": resolved_ref,
        "km_raw": camera.km_raw,
        "km": camera.km,
        "direction_raw": camera.direction_raw,
        "bearing_deg": camera.bearing_deg,
        "comune": camera.comune,
        "province": camera.province,
        "lat": None,
        "lon": None,
        "geocode_method": "none",
        "geocode_confidence": "none",
        "verified": False,
    }

    if not resolved_ref or camera.km is None:
        return record

    geometry = query_road_geometry(resolved_ref, camera.province, cache_dir=cache_dir)
    if not geometry:
        return record

    point = point_at_km(geometry, camera.km)
    if point is None:
        return record

    record["lon"], record["lat"] = point[0], point[1]
    record["geocode_method"] = "overpass_interpolated"
    record["geocode_confidence"] = "medium"
    return record
