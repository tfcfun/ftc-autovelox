import XCTest
@testable import VeloxKit

/// Live mode watches your position against every published stretch, with no
/// route to constrain it. That makes false positives the main risk: the whole
/// country is in scope, so "near something" must mean genuinely on it.
final class LiveMonitorTests: XCTestCase {
    private func snapshot() throws -> Snapshot {
        let base = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures", withExtension: nil))
        return try Snapshot.load(from: base.appendingPathComponent("snapshot"))
    }

    private func fix(lat: Double, lon: Double, speed: Double = 25,
                     course: Double? = 90, at t: TimeInterval = 0) -> Fix {
        Fix(coordinate: Coordinate(lat: lat, lon: lon), courseDegrees: course,
            speedMetresPerSecond: speed, timestamp: t)
    }

    func testAlertsWhenDrivingOntoAMonitoredStretch() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        // On the A4 stretch carried by the fixture.
        let alert = monitor.consume(fix(lat: 45.6612, lon: 12.5342))
        XCTAssertNotNil(alert)
        XCTAssertEqual(alert?.kind, .fixedCamera)
    }

    func testSilentWhenNowhereNearAnything() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        // Middle of the Adriatic.
        XCTAssertNil(monitor.consume(fix(lat: 43.0, lon: 15.0)))
    }

    func testAlertsOnlyOncePerStretch() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        XCTAssertNotNil(monitor.consume(fix(lat: 45.6612, lon: 12.5342, at: 0)))
        XCTAssertNil(monitor.consume(fix(lat: 45.6613, lon: 12.5344, at: 5)))
        XCTAssertNil(monitor.consume(fix(lat: 45.6614, lon: 12.5346, at: 10)))
    }

    func testLeavingAndReturningMuchLaterAlertsAgain() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        XCTAssertNotNil(monitor.consume(fix(lat: 45.6612, lon: 12.5342, at: 0)))
        // Drive away, then come back after the re-arm window.
        XCTAssertNil(monitor.consume(fix(lat: 45.0, lon: 12.0, at: 100)))
        XCTAssertNotNil(monitor.consume(fix(lat: 45.6612, lon: 12.5342,
                                            at: LiveMonitor.reArmSeconds + 200)))
    }

    func testStationaryIsSuppressed() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        XCTAssertNil(monitor.consume(fix(lat: 45.6612, lon: 12.5342, speed: 0.4)))
    }

    func testAMobileCheckAlertsOnlyOnItsScheduledDay() throws {
        // The fixture has an SS9/LO check on 2026-08-14 with segment geometry.
        let onDay = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        XCTAssertNotNil(onDay.consume(fix(lat: 45.305, lon: 9.520)))

        let otherDay = LiveMonitor(snapshot: try snapshot(), date: "2026-08-13")
        XCTAssertNil(otherDay.consume(fix(lat: 45.305, lon: 9.520)))
    }

    func testAParallelRoadDoesNotTrigger() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-14")
        // ~500 m north of the A4 stretch: a different road entirely.
        XCTAssertNil(monitor.consume(fix(lat: 45.6657, lon: 12.5342)))
    }

    func testDateCanBeChangedAsMidnightPasses() throws {
        let monitor = LiveMonitor(snapshot: try snapshot(), date: "2026-08-13")
        XCTAssertNil(monitor.consume(fix(lat: 45.305, lon: 9.520)))
        monitor.setDate("2026-08-14")
        XCTAssertNotNil(monitor.consume(fix(lat: 45.305, lon: 9.520)))
    }
}
