from velox.cli import build_mobile_records, deduplicate_cameras, iso_week


def test_deduplicate_collapses_the_same_physical_camera_filed_under_two_regions():
    # The real ordinary-roads PDF prints this row twice: once unlabelled inside
    # the Campania block, once under Basilicata.
    shared = {
        "network": "ordinaria", "road_name": "Potenza - Melfi", "km_raw": "2+600",
        "direction_raw": "Nord", "comune": "Potenza", "province": "PZ",
    }
    cameras = [
        {**shared, "region": "Campania", "id": "fx-ordi-Potenza-2600-nord"},
        {**shared, "region": "Basilicata", "id": "fx-ordi-Potenza-2600-nord"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 1
    assert len(kept) == 1


def test_deduplicate_keeps_genuinely_different_cameras_on_the_same_road():
    base = {"network": "ordinaria", "road_name": "Del Vesuvio", "region": "Campania",
            "province": "NA"}
    cameras = [
        {**base, "km_raw": "11+500", "direction_raw": "Sud", "comune": "Nola", "id": "a"},
        {**base, "km_raw": "4+190", "direction_raw": "Nord", "comune": "Sant'Anastasia",
         "id": "b"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 0
    assert len(kept) == 2


def test_deduplicate_keeps_both_carriageways_at_the_same_kilometre():
    base = {"network": "autostrada", "road_name": "Torino – Trieste", "region": "Veneto",
            "km_raw": "417+900", "comune": "Meolo", "province": "VE"}
    cameras = [
        {**base, "direction_raw": "Ovest", "id": "a"},
        {**base, "direction_raw": "Est", "id": "b"},
    ]
    kept, dropped = deduplicate_cameras(cameras)
    assert dropped == 0, "opposite carriageways are two separate installations"


def test_iso_week_formats_as_year_dash_w_week():
    assert iso_week("2026-08-13") == "2026-W33"
    assert iso_week("2026-01-01") == "2026-W01"


def test_build_mobile_records_assigns_ids_and_segment_links():
    from velox.parse_mobile import MobileCheck

    checks = [
        MobileCheck(date="2026-08-14", region="Lombardia", road_type="Strada Statale",
                    road_ref="SS9", road_name="via Emilia", province="LO"),
        MobileCheck(date="2026-08-15", region="Lombardia", road_type="Autostrada",
                    road_ref=None, road_name="Tangenziale", province="PV"),
    ]
    records = build_mobile_records(checks, week="2026-W33", segment_ids={"SS9_LO"})

    assert records[0]["id"] == "mb-2026W33-LO-SS9-2026-08-14"
    assert records[0]["segment_id"] == "seg-SS9-LO"
    assert records[1]["segment_id"] is None, "no ref means no geometry link"
