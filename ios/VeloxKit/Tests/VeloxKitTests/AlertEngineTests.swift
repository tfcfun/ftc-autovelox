import XCTest
@testable import VeloxKit

final class AlertEngineTests: XCTestCase {
    /// A straight west-to-east road at latitude 45.
    private func eastboundRoute(points: Int = 200) -> [Coordinate] {
        (0..<points).map { Coordinate(lat: 45.0, lon: 9.0 + Double($0) * 0.001) }
    }

    private func camera(bearing: Int?, lon: Double = 9.100) -> FixedCamera {
        FixedCamera(
            id: "fx-test", network: "autostrada", region: "Lombardia",
            roadName: "Test", roadRef: "A99", kmRaw: "1+000", km: 1.0,
            directionRaw: bearing.map { _ in "Est" }, bearingDeg: bearing,
            comune: "Test", province: "LO", lat: 45.0, lon: lon,
            geocodeConfidence: "high", verified: true
        )
    }

    private func drive(_ engine: AlertEngine, from startLon: Double, to endLon: Double,
                       course: Double, steps: Int = 400, speed: Double = 30) -> [Alert] {
        var alerts: [Alert] = []
        for step in 0...steps {
            let ratio = Double(step) / Double(steps)
            let fix = Fix(
                coordinate: Coordinate(lat: 45.0, lon: startLon + (endLon - startLon) * ratio),
                courseDegrees: course, speedMetresPerSecond: speed,
                timestamp: Double(step)
            )
            if let alert = engine.consume(fix) { alerts.append(alert) }
        }
        return alerts
    }

    func testFixedCameraAlertsOnceWhenApproachingInTheRightDirection() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: 90), alongTrackMetres: 7_800)], route: route
        )
        let alerts = drive(engine, from: 9.000, to: 9.150, course: 90)
        XCTAssertEqual(alerts.count, 1, "exactly one alert per camera per trip")
        XCTAssertEqual(alerts.first?.kind, .fixedCamera)
    }

    func testWrongDirectionProducesNoAlert() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: 270), alongTrackMetres: 7_800)], route: route
        )
        let alerts = drive(engine, from: 9.000, to: 9.150, course: 90)
        XCTAssertTrue(alerts.isEmpty,
                      "a westbound camera must stay silent for eastbound traffic")
    }

    func testCameraWithoutADirectionAlertsRegardlessOfCourse() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: nil), alongTrackMetres: 7_800)], route: route
        )
        XCTAssertEqual(drive(engine, from: 9.000, to: 9.150, course: 90).count, 1)
    }

    func testAlertFiresWithinTheApproachWindowNotEarlier() {
        let route = eastboundRoute()
        let target = camera(bearing: 90, lon: 9.100)
        let engine = AlertEngine(findings: [.fixed(target, alongTrackMetres: 7_800)], route: route)
        // Stop 3 km short: no alert should have fired yet.
        let alerts = drive(engine, from: 9.000, to: 9.060, course: 90)
        XCTAssertTrue(alerts.isEmpty)
    }

    func testStationaryVehicleIsSuppressed() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: 90), alongTrackMetres: 7_800)], route: route
        )
        let alerts = drive(engine, from: 9.000, to: 9.150, course: 90, speed: 0.5)
        XCTAssertTrue(alerts.isEmpty, "parked or walking must not trigger driving alerts")
    }

    func testOffRoadPositionIsSuppressed() {
        // 1 km north of the route: the overpass case.
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: 90), alongTrackMetres: 7_800)], route: route
        )
        var alerts: [Alert] = []
        for step in 0...400 {
            let fix = Fix(
                coordinate: Coordinate(lat: 45.010, lon: 9.0 + Double(step) * 0.0004),
                courseDegrees: 90, speedMetresPerSecond: 30, timestamp: Double(step)
            )
            if let alert = engine.consume(fix) { alerts.append(alert) }
        }
        XCTAssertTrue(alerts.isEmpty)
    }

    func testScheduledRoadFiresOnceOnEntry() {
        let route = eastboundRoute()
        let check = MobileCheck(
            id: "mb-test", date: "2026-08-14", week: "2026-W33", region: "Lombardia",
            roadType: "Strada Statale", roadRef: "SS9", roadName: "via Emilia",
            province: "LO", segmentId: "seg-SS9-LO"
        )
        let engine = AlertEngine(findings: [.mobile(check, alongTrackMetres: 2_000)], route: route)
        let alerts = drive(engine, from: 9.000, to: 9.150, course: 90)
        XCTAssertEqual(alerts.count, 1)
        XCTAssertEqual(alerts.first?.kind, .scheduledRoad)
    }

    func testAlertCopyNamesTheLimitAndNeverTheFine() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(bearing: 90), alongTrackMetres: 7_800)], route: route
        )
        let alert = try? XCTUnwrap(drive(engine, from: 9.000, to: 9.150, course: 90).first)
        let message = (alert?.message ?? "").lowercased()
        XCTAssertTrue(message.contains("limite"))
        for forbidden in ["multa", "sanzione", "evita", "rallenta per non"] {
            XCTAssertFalse(message.contains(forbidden), "alert copy must not mention \(forbidden)")
        }
    }
}

// MARK: - Placement confidence

extension AlertEngineTests {
    private func camera(confidence: String, verified: Bool) -> FixedCamera {
        FixedCamera(
            id: "fx-conf-\(confidence)-\(verified)", network: "ordinaria", region: "Campania",
            roadName: "Del Vesuvio", roadRef: nil, kmRaw: "11+500", km: 11.5,
            directionRaw: nil, bearingDeg: nil, comune: "Nola", province: "NA",
            lat: 45.0, lon: 9.100, geocodeConfidence: confidence, verified: verified
        )
    }

    /// Fixed cameras are placed from their comune, which is accurate to roughly
    /// 1-2 km. Firing an 800 m warning off a 2 km guess cries wolf, and a driver
    /// who learns to ignore the app is worse off than one who never installed it.
    func testLowConfidenceUnverifiedCameraNeverAlerts() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(confidence: "low", verified: false),
                              alongTrackMetres: 7_800)],
            route: route
        )
        XCTAssertTrue(drive(engine, from: 9.000, to: 9.150, course: 90).isEmpty)
    }

    func testAHumanVerifiedCameraAlertsEvenAtLowConfidence() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(confidence: "low", verified: true),
                              alongTrackMetres: 7_800)],
            route: route
        )
        XCTAssertEqual(drive(engine, from: 9.000, to: 9.150, course: 90).count, 1,
                       "review is what makes a point trustworthy")
    }

    func testHighConfidenceCameraAlertsWithoutReview() {
        let route = eastboundRoute()
        let engine = AlertEngine(
            findings: [.fixed(camera(confidence: "high", verified: false),
                              alongTrackMetres: 7_800)],
            route: route
        )
        XCTAssertEqual(drive(engine, from: 9.000, to: 9.150, course: 90).count, 1)
    }

    func testScheduledRoadStillAlertsRegardlessOfCameraConfidence() {
        let route = eastboundRoute()
        let check = MobileCheck(
            id: "mb-conf", date: "2026-08-14", week: "2026-W33", region: "Lombardia",
            roadType: "Strada Statale", roadRef: "SS9", roadName: "via Emilia",
            province: "LO", segmentId: "seg-SS9-LO"
        )
        let engine = AlertEngine(findings: [.mobile(check, alongTrackMetres: 2_000)],
                                 route: route)
        XCTAssertEqual(drive(engine, from: 9.000, to: 9.150, course: 90).count, 1,
                       "a scheduled road is not a placed point and is unaffected")
    }
}

// MARK: - Stretch entry

extension AlertEngineTests {
    private func stretchCamera(_ stretch: [[Double]]) -> FixedCamera {
        FixedCamera(
            id: "fx-stretch", network: "autostrada", region: "Lombardia",
            roadName: "Torino – Trieste", roadRef: "A4", kmRaw: "423+850", km: 423.85,
            directionRaw: nil, bearingDeg: nil, comune: "Test", province: "LO",
            lat: 45.0, lon: 9.05, geocodeConfidence: "low", verified: false,
            uncertaintyWays: [stretch]
        )
    }

    /// A stretch is a real, detectable event: you either are on it or you are not.
    /// It warrants a one-shot warning on entry, unlike a distance countdown to a
    /// point we never had.
    func testEnteringAStretchAlertsOnce() {
        let route = eastboundRoute()
        let stretch = (0...30).map { [9.05 + Double($0) * 0.001, 45.0] }
        let engine = AlertEngine(
            findings: [.fixed(stretchCamera(stretch), alongTrackMetres: 3_900)],
            route: route
        )
        let alerts = drive(engine, from: 9.000, to: 9.150, course: 90)
        XCTAssertEqual(alerts.count, 1, "one warning per stretch per trip")
        XCTAssertEqual(alerts.first?.kind, .fixedCamera)
    }

    func testTheStretchWarningDoesNotClaimADistance() {
        let route = eastboundRoute()
        let stretch = (0...30).map { [9.05 + Double($0) * 0.001, 45.0] }
        let engine = AlertEngine(
            findings: [.fixed(stretchCamera(stretch), alongTrackMetres: 3_900)],
            route: route
        )
        let alert = drive(engine, from: 9.000, to: 9.150, course: 90).first
        XCTAssertNil(alert?.distanceMetres,
                     "we do not know where along the stretch it is, so claim no distance")
        let message = (alert?.message ?? "").lowercased()
        XCTAssertTrue(message.contains("limite"))
        XCTAssertFalse(message.contains("metri"), "no invented distance in the copy")
    }

    func testAStretchNotYetReachedStaysSilent() {
        let route = eastboundRoute()
        let stretch = (0...30).map { [9.12 + Double($0) * 0.001, 45.0] }
        let engine = AlertEngine(
            findings: [.fixed(stretchCamera(stretch), alongTrackMetres: 9_400)],
            route: route
        )
        // Stop well before the stretch begins.
        XCTAssertTrue(drive(engine, from: 9.000, to: 9.050, course: 90).isEmpty)
    }
}
