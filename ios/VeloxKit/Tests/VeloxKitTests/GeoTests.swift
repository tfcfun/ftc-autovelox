import XCTest
@testable import VeloxKit

final class GeoTests: XCTestCase {
    private let milan = Coordinate(lat: 45.4642, lon: 9.1900)
    private let bologna = Coordinate(lat: 44.4949, lon: 11.3426)

    func testDistanceMatchesAKnownSeparation() {
        // Milan to Bologna is about 200 km great-circle.
        let metres = Geo.distance(milan, bologna)
        XCTAssertEqual(metres, 200_000, accuracy: 8_000)
    }

    func testDistanceToSelfIsZero() {
        XCTAssertEqual(Geo.distance(milan, milan), 0, accuracy: 0.001)
    }

    func testBearingNorthAndEast() {
        let north = Coordinate(lat: 46.0, lon: 9.19)
        let east = Coordinate(lat: 45.4642, lon: 10.0)
        XCTAssertEqual(Geo.bearing(from: milan, to: north), 0, accuracy: 1)
        XCTAssertEqual(Geo.bearing(from: milan, to: east), 90, accuracy: 1)
    }

    func testAngularDifferenceWrapsAroundNorth() {
        XCTAssertEqual(Geo.angularDifference(350, 10), 20, accuracy: 0.001)
        XCTAssertEqual(Geo.angularDifference(10, 350), 20, accuracy: 0.001)
        XCTAssertEqual(Geo.angularDifference(0, 180), 180, accuracy: 0.001)
        XCTAssertEqual(Geo.angularDifference(90, 90), 0, accuracy: 0.001)
    }

    func testDistanceToPolylineUsesPerpendicularNotVertices() {
        let line = [Coordinate(lat: 45.0, lon: 9.0), Coordinate(lat: 45.0, lon: 9.1)]
        // A point directly above the middle of the segment, ~1.1 km north.
        let point = Coordinate(lat: 45.01, lon: 9.05)
        let distance = Geo.distanceToPolyline(point, polyline: line)
        XCTAssertEqual(distance, 1_112, accuracy: 60)
    }

    func testDistanceToEmptyPolylineIsInfinite() {
        XCTAssertEqual(Geo.distanceToPolyline(milan, polyline: []), .infinity)
    }

    func testAlongTrackDistanceOrdersPointsByProgress() {
        let line = [
            Coordinate(lat: 45.0, lon: 9.0),
            Coordinate(lat: 45.0, lon: 9.1),
            Coordinate(lat: 45.0, lon: 9.2),
        ]
        let early = Geo.alongTrackDistance(Coordinate(lat: 45.0, lon: 9.02), polyline: line)
        let late = Geo.alongTrackDistance(Coordinate(lat: 45.0, lon: 9.18), polyline: line)
        XCTAssertLessThan(early, late)
        XCTAssertGreaterThan(early, 0)
    }

    func testPolylinesIntersectWhenTheyOverlap() {
        let a = [Coordinate(lat: 45.0, lon: 9.0), Coordinate(lat: 45.0, lon: 9.2)]
        let b = [Coordinate(lat: 45.0, lon: 9.1), Coordinate(lat: 45.0, lon: 9.3)]
        XCTAssertTrue(Geo.polylinesIntersect(a, b, toleranceMetres: 30))
    }

    func testParallelRoadOneHundredMetresAwayDoesNotIntersect() {
        let a = [Coordinate(lat: 45.0, lon: 9.0), Coordinate(lat: 45.0, lon: 9.2)]
        let b = [Coordinate(lat: 45.0009, lon: 9.0), Coordinate(lat: 45.0009, lon: 9.2)]
        XCTAssertGreaterThan(Geo.distance(a[0], b[0]), 90)
        XCTAssertFalse(Geo.polylinesIntersect(a, b, toleranceMetres: 30),
                       "a parallel road 100 m away must not count as the same road")
    }
}
