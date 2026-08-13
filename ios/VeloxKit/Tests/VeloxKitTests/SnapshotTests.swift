import XCTest
@testable import VeloxKit

final class SnapshotTests: XCTestCase {
    private func fixtureURL() throws -> URL {
        let base = Bundle.module.url(forResource: "Fixtures", withExtension: nil)
        return try XCTUnwrap(base).appendingPathComponent("snapshot")
    }

    func testDecodesTheFixtureSnapshot() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        XCTAssertEqual(snapshot.index.schemaVersion, 1)
        XCTAssertEqual(snapshot.index.week, "2026-W33")
        XCTAssertEqual(snapshot.fixedCameras.count, 2)
        XCTAssertEqual(snapshot.mobileChecks.count, 2)
        XCTAssertEqual(snapshot.roadSegments.count, 1)
        XCTAssertEqual(snapshot.mitDevices.count, 2)
    }

    func testNullCoordinatesDecodeAsNilRatherThanZero() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        let unplaced = try XCTUnwrap(snapshot.fixedCameras.first { $0.id.contains("A1") })
        XCTAssertNil(unplaced.lat)
        XCTAssertNil(unplaced.lon)
        XCTAssertNil(unplaced.coordinate, "an unplaced camera must not become 0,0")
    }

    func testPlacedCameraExposesACoordinate() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        let placed = try XCTUnwrap(snapshot.fixedCameras.first { $0.id.contains("A4") })
        let coordinate = try XCTUnwrap(placed.coordinate)
        XCTAssertEqual(coordinate.lat, 45.6612, accuracy: 0.0001)
        XCTAssertEqual(coordinate.lon, 12.5341, accuracy: 0.0001)
    }

    func testRegionStatusesDecode() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        XCTAssertEqual(snapshot.index.regions["Lombardia"]?.status, "ok")
        XCTAssertEqual(snapshot.index.regions["Sicilia"]?.status, "stale")
    }

    func testUnsupportedSchemaVersionIsRejectedNotPartiallyDecoded() throws {
        let json = #"{"schema_version": 99, "generated_at": "x", "week": "w", "files": {}, "regions": {}, "sources": {}, "quarantine_count": 0}"#
        let data = try XCTUnwrap(json.data(using: .utf8))
        XCTAssertThrowsError(try SnapshotIndex.decode(from: data)) { error in
            guard case SnapshotError.unsupportedSchema(let version) = error else {
                return XCTFail("expected unsupportedSchema, got \(error)")
            }
            XCTAssertEqual(version, 99)
        }
    }
}

// MARK: - Areas of uncertainty

extension SnapshotTests {
    /// The sources give a road and a comune, never a coordinate, so most cameras
    /// are known only as the stretch they sit somewhere along.
    func testDecodesUncertaintyStretches() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        let withExtent = snapshot.fixedCameras.first { !$0.uncertaintyWays.isEmpty }
        let camera = try XCTUnwrap(withExtent, "the fixture must carry a stretch")
        XCTAssertGreaterThanOrEqual(camera.uncertaintyStretches.first?.count ?? 0, 2)
    }

    func testStretchCoordinatesAreLatLonNotLonLat() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        for camera in snapshot.fixedCameras {
            for stretch in camera.uncertaintyStretches {
                for point in stretch {
                    // Italy: latitude 35-48, longitude 6-19. Swapping them puts
                    // every camera in the sea off Somalia.
                    XCTAssertTrue((35...48).contains(point.lat), "lat \(point.lat)")
                    XCTAssertTrue((6...19).contains(point.lon), "lon \(point.lon)")
                }
            }
        }
    }

    func testACameraWithAStretchIsLocatedEvenWithoutATrustedPoint() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        let camera = try XCTUnwrap(snapshot.fixedCameras.first { !$0.uncertaintyWays.isEmpty })
        XCTAssertTrue(camera.isLocated)
        XCTAssertFalse(camera.isTrustworthyForProximityAlerts,
                       "a stretch is not a point and must never drive a distance countdown")
    }

    func testAnUnlocatedCameraReportsItself() throws {
        let camera = FixedCamera(
            id: "fx-none", network: "ordinaria", region: "Lombardia", roadName: "?",
            roadRef: nil, kmRaw: "1+000", km: 1, directionRaw: nil, bearingDeg: nil,
            comune: "Meseno", province: "MI", lat: nil, lon: nil,
            geocodeConfidence: "none", verified: false, uncertaintyWays: []
        )
        XCTAssertFalse(camera.isLocated)
    }
}

// MARK: - Coverage window

extension SnapshotTests {
    /// The date picker must offer only days the published programme covers.
    /// Deriving that from the ISO week number is a guess; the PDF states it.
    func testCoverageWindowComesFromTheSource() throws {
        let snapshot = try Snapshot.load(from: fixtureURL())
        let coverage = try XCTUnwrap(snapshot.index.coverage)

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Europe/Rome")
        XCTAssertEqual(formatter.string(from: coverage.from), "2026-08-10")
        XCTAssertEqual(formatter.string(from: coverage.to), "2026-08-16")
    }

    func testCoverageIsNilWhenTheSourceDidNotStateIt() throws {
        let json = #"{"schema_version":1,"generated_at":"2026-08-13T06:00:00Z","week":"2026-W33","regions":{},"quarantine_count":0}"#
        let index = try SnapshotIndex.decode(from: XCTUnwrap(json.data(using: .utf8)))
        XCTAssertNil(index.coverage, "no window stated means no window claimed")
    }
}
