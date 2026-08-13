import XCTest
@testable import VeloxKit

final class RouteMatcherTests: XCTestCase {
    private func snapshot() throws -> Snapshot {
        let base = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures", withExtension: nil))
        return try Snapshot.load(from: base.appendingPathComponent("snapshot"))
    }

    /// A route running along the SS9 fixture segment.
    private var routeAlongSS9: [Coordinate] {
        [Coordinate(lat: 45.300, lon: 9.500),
         Coordinate(lat: 45.305, lon: 9.520),
         Coordinate(lat: 45.310, lon: 9.540)]
    }

    func testMobileCheckMatchesOnItsScheduledDate() throws {
        let findings = RouteMatcher.findings(
            route: routeAlongSS9, snapshot: try snapshot(), date: "2026-08-14"
        )
        let mobile = findings.compactMap { if case .mobile(let c, _) = $0 { return c } else { return nil } }
        XCTAssertEqual(mobile.count, 1)
        XCTAssertEqual(mobile.first?.roadRef, "SS9")
    }

    func testMobileCheckIsSilentOnAnotherDate() throws {
        let findings = RouteMatcher.findings(
            route: routeAlongSS9, snapshot: try snapshot(), date: "2026-08-13"
        )
        XCTAssertTrue(findings.isEmpty, "a check scheduled for the 14th must not appear on the 13th")
    }

    func testMobileCheckWithoutGeometryIsNeverMatched() throws {
        // The A7/PV fixture row has segment_id null; no geometry means no route match.
        let findings = RouteMatcher.findings(
            route: routeAlongSS9, snapshot: try snapshot(), date: "2026-08-15"
        )
        XCTAssertTrue(findings.isEmpty)
    }

    func testFixedCameraWithinTheCorridorIsFound() throws {
        let route = [Coordinate(lat: 45.6600, lon: 12.5330),
                     Coordinate(lat: 45.6625, lon: 12.5355)]
        let findings = RouteMatcher.findings(route: route, snapshot: try snapshot(), date: "2026-01-01")
        let fixed = findings.compactMap { if case .fixed(let c, _) = $0 { return c } else { return nil } }
        XCTAssertEqual(fixed.count, 1)
        XCTAssertEqual(fixed.first?.roadRef, "A4")
    }

    func testUnplacedFixedCameraIsNeverMatched() throws {
        let route = [Coordinate(lat: 0.0, lon: 0.0), Coordinate(lat: 0.001, lon: 0.001)]
        let findings = RouteMatcher.findings(route: route, snapshot: try snapshot(), date: "2026-01-01")
        XCTAssertTrue(findings.isEmpty, "a camera with null coordinates must never match 0,0")
    }

    func testFindingsAreOrderedByProgressAlongTheRoute() throws {
        let route = routeAlongSS9
        let findings = RouteMatcher.findings(route: route, snapshot: try snapshot(), date: "2026-08-14")
        let distances = findings.map(\.alongTrackMetres)
        XCTAssertEqual(distances, distances.sorted())
    }

    func testDistantRouteFindsNothing() throws {
        let route = [Coordinate(lat: 38.11, lon: 13.36), Coordinate(lat: 38.12, lon: 13.37)]
        let findings = RouteMatcher.findings(route: route, snapshot: try snapshot(), date: "2026-08-14")
        XCTAssertTrue(findings.isEmpty)
    }
}

// MARK: - Stretch-located cameras

extension RouteMatcherTests {
    private func stretchCamera(along stretch: [[Double]]) -> FixedCamera {
        FixedCamera(
            id: "fx-stretch", network: "autostrada", region: "Veneto",
            roadName: "Torino – Trieste", roadRef: "A4", kmRaw: "423+850", km: 423.85,
            directionRaw: "Ovest", bearingDeg: 270, comune: "Noventa di Piave",
            province: "VE", lat: 45.60, lon: 12.470,
            geocodeConfidence: "low", verified: false, uncertaintyWays: [stretch]
        )
    }

    /// A camera known only as a stretch must be found when the route touches ANY
    /// part of it - including when the stretch's centre, which is all the old
    /// point logic had, sits far outside the corridor.
    func testRouteTouchingOnlyTheStretchEndFindsTheCamera() {
        // ~11 km of road running east; its centre is ~5 km from either end.
        let stretch = (0...20).map { [12.40 + Double($0) * 0.007, 45.60] }
        // The route overlaps only the western tip.
        let route = [Coordinate(lat: 45.60, lon: 12.400),
                     Coordinate(lat: 45.60, lon: 12.410)]
        let snapshot = Snapshot(
            index: try! SnapshotIndex.decode(from: Data(#"""
            {"schema_version":1,"generated_at":"2026-08-13T06:00:00Z","week":"2026-W33",
             "regions":{},"quarantine_count":0}
            """#.utf8)),
            fixedCameras: [stretchCamera(along: stretch)],
            mobileChecks: [], roadSegments: [], mitDevices: []
        )
        // Guard the guard: the framing centre must be OUTSIDE the point corridor,
        // or this test would pass on the old logic and prove nothing.
        let centre = Coordinate(lat: 45.60, lon: 12.470)
        XCTAssertGreaterThan(Geo.distanceToPolyline(centre, polyline: route), 500)

        let findings = RouteMatcher.findings(route: route, snapshot: snapshot,
                                             date: "2026-08-13")
        XCTAssertEqual(findings.count, 1, "the stretch touches the route")
    }

    func testARouteFarFromTheStretchFindsNothing() {
        let stretch = [[12.5280, 45.6690], [12.5342, 45.6738]]
        // Palermo.
        let route = [Coordinate(lat: 38.11, lon: 13.36), Coordinate(lat: 38.12, lon: 13.37)]
        let snapshot = Snapshot(
            index: try! SnapshotIndex.decode(from: Data(#"""
            {"schema_version":1,"generated_at":"2026-08-13T06:00:00Z","week":"2026-W33",
             "regions":{},"quarantine_count":0}
            """#.utf8)),
            fixedCameras: [stretchCamera(along: stretch)],
            mobileChecks: [], roadSegments: [], mitDevices: []
        )
        XCTAssertTrue(RouteMatcher.findings(route: route, snapshot: snapshot,
                                            date: "2026-08-13").isEmpty)
    }
}
