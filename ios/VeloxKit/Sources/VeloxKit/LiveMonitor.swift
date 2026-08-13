import Foundation

/// Watches your position against every published stretch, with no planned route.
///
/// Trip mode has a route to constrain it: only findings along that line can ever
/// fire. Live mode has the whole country in scope, so the risk profile inverts —
/// the danger is no longer missing a warning but crying wolf, and a driver who
/// learns to ignore the app is worse off than one who never installed it.
///
/// Three things keep it honest:
///
/// * **Proximity is strict.** You must be within `corridorMetres` of the road
///   itself, not merely in the same area. A parallel road 500 m away is a
///   different road.
/// * **Once per stretch.** Re-arming only after `reArmSeconds` away from it, so a
///   slow crawl along a monitored road does not repeat.
/// * **Only what is trustworthy.** A camera placed from its comune is accurate to
///   roughly 1–2 km, so it alerts on entering its *stretch*, never as a distance
///   countdown to a point the sources never published.
public final class LiveMonitor {
    /// How close to the road counts as being on it.
    public static let corridorMetres: Double = 40

    /// A stretch can alert again only after this long away from it.
    public static let reArmSeconds: TimeInterval = 1_800

    /// Below this you are parked, walking, or in traffic — not worth warning.
    public static let minimumSpeedMetresPerSecond: Double = 3.0

    private let snapshot: Snapshot
    private var date: String
    private var lastFired: [String: TimeInterval] = [:]

    public init(snapshot: Snapshot, date: String) {
        self.snapshot = snapshot
        self.date = date
    }

    /// Update the calendar day, so a drive across midnight uses the right
    /// schedule rather than yesterday's.
    public func setDate(_ newDate: String) {
        date = newDate
    }

    /// One position in, at most one alert out.
    public func consume(_ fix: Fix) -> Alert? {
        guard fix.speedMetresPerSecond >= Self.minimumSpeedMetresPerSecond else { return nil }

        for camera in snapshot.fixedCameras {
            let stretches = camera.uncertaintyStretches
            guard !stretches.isEmpty else { continue }
            guard stretches.contains(where: {
                Geo.distanceToPolyline(fix.coordinate, polyline: $0) <= Self.corridorMetres
            }) else { continue }
            guard shouldFire(id: camera.id, at: fix.timestamp) else { continue }
            return Alert(
                id: camera.id, kind: .fixedCamera,
                message: Copy.stretchEntryAlert(road: camera.roadRef ?? camera.roadName),
                distanceMetres: nil
            )
        }

        let segmentsById = Dictionary(
            uniqueKeysWithValues: snapshot.roadSegments.map { ($0.id, $0) }
        )
        for check in snapshot.mobileChecks where check.date == date {
            guard let segmentId = check.segmentId,
                  let segment = segmentsById[segmentId] else { continue }
            guard Geo.distanceToPolyline(fix.coordinate, polyline: segment.coordinates)
                    <= Self.corridorMetres else { continue }
            guard shouldFire(id: check.id, at: fix.timestamp) else { continue }
            return Alert(
                id: check.id, kind: .scheduledRoad,
                message: Copy.scheduledRoadAlert(
                    road: check.roadRef ?? check.roadName ?? "questa strada",
                    province: check.province
                ),
                distanceMetres: nil
            )
        }

        return nil
    }

    /// True when this stretch has not fired recently.
    ///
    /// Records the time on every proximate fix, not only on firing, so the
    /// re-arm window measures time *away* from the stretch rather than time
    /// since the last warning — otherwise a long drive along one monitored road
    /// would warn again every half hour without you ever leaving it.
    private func shouldFire(id: String, at timestamp: TimeInterval) -> Bool {
        defer { lastFired[id] = timestamp }
        guard let previous = lastFired[id] else { return true }
        return timestamp - previous >= Self.reArmSeconds
    }
}
