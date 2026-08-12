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
