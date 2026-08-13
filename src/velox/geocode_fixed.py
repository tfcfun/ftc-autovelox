"""Locate a fixed camera as precisely as the source actually allows.

The source never gives a coordinate. It gives a road, a kilometre, a comune and
usually a direction. So there are two honest outcomes:

* A usable road reference plus a kilometre lets us interpolate an actual point.
  Marked "medium" - Italian kilometre posts count from historical origins that
  do not always coincide with the start of the OSM way.

* Otherwise we know the camera is somewhere along the roads of its class inside
  its comune. That is a STRETCH, not a point, and it is published as one in
  `uncertainty_ways`. Drawing a pin there would claim a precision the source does
  not contain; drawing the stretch says exactly what is known.

`lat`/`lon` on a stretch-located camera exist only to frame the map. Nothing
should treat them as the camera's position.
"""

from __future__ import annotations

from pathlib import Path

from velox.geocode_comune import locate as locate_by_comune
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
        # The stretches the camera sits somewhere along. Empty when unknown.
        "uncertainty_ways": [],
    }

    if resolved_ref and camera.km is not None:
        geometry = query_road_geometry(resolved_ref, camera.province, cache_dir=cache_dir)
        point = point_at_km(geometry, camera.km) if geometry else None
        if point is not None:
            record["lon"], record["lat"] = point[0], point[1]
            record["geocode_method"] = "overpass_interpolated"
            record["geocode_confidence"] = "medium"
            return record

    # No usable reference: the PDFs name roads descriptively. Fall back to the
    # comune, which yields both the reference and a point on the right road.
    # Deliberately low confidence - good enough to review, never to alert on.
    located = locate_by_comune(camera.comune, camera.province, camera.network)
    if located is None:
        return record

    record["road_ref"] = record["road_ref"] or located["ref"]
    record["lon"], record["lat"] = located["lon"], located["lat"]
    record["uncertainty_ways"] = located.get("ways") or []
    # The point is a map-framing centre, not a claim. The stretches are the claim.
    record["geocode_method"] = "comune_road_extent"
    record["geocode_confidence"] = "low"
    return record


def geocode_stub(camera: FixedCamera) -> dict:
    """The record a camera gets when geocoding failed outright.

    Published deliberately: the installation is real and belongs in the region
    browse even when it cannot be placed. Null coordinates keep it off the map
    and out of proximity alerts.
    """
    return {
        "id": "-".join([
            "fx", camera.network[:4], (camera.road_ref or camera.comune or "x"),
            camera.km_raw.replace("+", "").replace(",", ""),
            (camera.direction_raw or "na").lower(),
        ]),
        "network": camera.network, "region": camera.region,
        "road_name": camera.road_name, "road_ref": camera.road_ref,
        "km_raw": camera.km_raw, "km": camera.km,
        "direction_raw": camera.direction_raw, "bearing_deg": camera.bearing_deg,
        "comune": camera.comune, "province": camera.province,
        "lat": None, "lon": None, "uncertainty_ways": [],
        "geocode_method": "failed", "geocode_confidence": "none", "verified": False,
    }
