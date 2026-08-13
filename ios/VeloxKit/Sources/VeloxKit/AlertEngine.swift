import Foundation

public struct Fix: Equatable, Sendable {
    public let coordinate: Coordinate
    public let courseDegrees: Double?
    public let speedMetresPerSecond: Double
    public let timestamp: TimeInterval

    public init(coordinate: Coordinate, courseDegrees: Double?,
                speedMetresPerSecond: Double, timestamp: TimeInterval) {
        self.coordinate = coordinate
        self.courseDegrees = courseDegrees
        self.speedMetresPerSecond = speedMetresPerSecond
        self.timestamp = timestamp
    }
}

public enum AlertKind: Equatable, Sendable {
    case fixedCamera
    case scheduledRoad
}

public struct Alert: Equatable, Identifiable, Sendable {
    public let id: String
    public let kind: AlertKind
    public let message: String
    public let distanceMetres: Double?
}

/// Turns a stream of position fixes into at most one alert per finding per trip.
///
/// Every suppression rule here exists because firing wrongly is worse than not
/// firing: a warning for the road beneath a viaduct, or for the opposite
/// carriageway, teaches the driver to ignore the app.
public final class AlertEngine {
    public static let approachWindowMetres: Double = 800
    public static let corridorMetres: Double = 30
    public static let minimumSpeedMetresPerSecond: Double = 3.0
    public static let directionToleranceDegrees: Double = 60

    private let findings: [Finding]
    private let route: [Coordinate]
    private var fired: Set<String> = []

    public init(findings: [Finding], route: [Coordinate]) {
        self.findings = findings
        self.route = route
    }

    public func consume(_ fix: Fix) -> Alert? {
        guard fix.speedMetresPerSecond >= Self.minimumSpeedMetresPerSecond else { return nil }
        guard Geo.distanceToPolyline(fix.coordinate, polyline: route) <= Self.corridorMetres
        else { return nil }

        let progress = Geo.alongTrackDistance(fix.coordinate, polyline: route)

        for finding in findings where !fired.contains(finding.id) {
            switch finding {
            case .fixed(let camera, let alongTrack):
                // Known only as a stretch: warn on ENTRY. Being on the stretch is
                // a fact we can detect; a distance to a point we never had is not.
                if !camera.uncertaintyStretches.isEmpty {
                    guard progress >= alongTrack else { continue }
                    fired.insert(finding.id)
                    return Alert(
                        id: finding.id, kind: .fixedCamera,
                        message: Copy.stretchEntryAlert(
                            road: camera.roadRef ?? camera.roadName
                        ),
                        distanceMetres: nil
                    )
                }

                // Most cameras are placed from their comune, which is accurate to
                // roughly 1-2 km, because the source PDFs name roads
                // descriptively and never by reference. An 800 m warning fired
                // off a 2 km guess cries wolf, and a driver who learns to ignore
                // the app is worse off than one who never installed it. Such a
                // camera still appears on the map and in the route list.
                guard camera.isTrustworthyForProximityAlerts else { continue }
                let remaining = alongTrack - progress
                guard remaining >= 0, remaining <= Self.approachWindowMetres else { continue }
                if let cameraBearing = camera.bearingDeg, let course = fix.courseDegrees {
                    let difference = Geo.angularDifference(Double(cameraBearing), course)
                    guard difference <= Self.directionToleranceDegrees else { continue }
                }
                fired.insert(finding.id)
                return Alert(
                    id: finding.id, kind: .fixedCamera,
                    message: Copy.fixedCameraAlert(metres: Int(remaining.rounded())),
                    distanceMetres: remaining
                )

            case .mobile(let check, let alongTrack):
                guard progress >= alongTrack else { continue }
                fired.insert(finding.id)
                return Alert(
                    id: finding.id, kind: .scheduledRoad,
                    message: Copy.scheduledRoadAlert(
                        road: check.roadRef ?? check.roadName ?? "questa strada",
                        province: check.province
                    ),
                    distanceMetres: nil
                )
            }
        }
        return nil
    }
}
