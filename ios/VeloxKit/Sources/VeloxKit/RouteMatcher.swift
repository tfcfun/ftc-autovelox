import Foundation

public enum Finding: Equatable, Identifiable, Sendable {
    case fixed(FixedCamera, alongTrackMetres: Double)
    case mobile(MobileCheck, alongTrackMetres: Double)

    public var id: String {
        switch self {
        case .fixed(let camera, _): return camera.id
        case .mobile(let check, _): return check.id
        }
    }

    public var alongTrackMetres: Double {
        switch self {
        case .fixed(_, let metres), .mobile(_, let metres): return metres
        }
    }
}

public enum RouteMatcher {
    /// Findings along `route` for a given calendar date, ordered by progress.
    ///
    /// A fixed camera without coordinates and a mobile check without geometry are
    /// both skipped: an unplaceable item is never guessed onto the map.
    public static func findings(
        route: [Coordinate],
        snapshot: Snapshot,
        date: String,
        fixedCorridorMetres: Double = 500,
        segmentToleranceMetres: Double = 30
    ) -> [Finding] {
        guard route.count >= 2 else { return [] }
        var results: [Finding] = []

        for camera in snapshot.fixedCameras {
            let stretches = camera.uncertaintyStretches
            if !stretches.isEmpty {
                // Known only as a stretch. Match if the route touches ANY of it -
                // the camera could be anywhere along it, so testing the middle
                // would miss a route that clips one end.
                let touching = stretches.filter {
                    Geo.polylinesIntersect(route, $0, toleranceMetres: segmentToleranceMetres)
                }
                guard !touching.isEmpty else { continue }
                let entry = touching
                    .flatMap { $0 }
                    .filter { Geo.distanceToPolyline($0, polyline: route) <= segmentToleranceMetres }
                    .map { Geo.alongTrackDistance($0, polyline: route) }
                    .min() ?? 0
                results.append(.fixed(camera, alongTrackMetres: entry))
                continue
            }

            guard let coordinate = camera.coordinate else { continue }
            let offset = Geo.distanceToPolyline(coordinate, polyline: route)
            guard offset <= fixedCorridorMetres else { continue }
            results.append(
                .fixed(camera, alongTrackMetres: Geo.alongTrackDistance(coordinate, polyline: route))
            )
        }

        let segmentsById = Dictionary(
            uniqueKeysWithValues: snapshot.roadSegments.map { ($0.id, $0) }
        )
        for check in snapshot.mobileChecks where check.date == date {
            guard let segmentId = check.segmentId,
                  let segment = segmentsById[segmentId] else { continue }
            let geometry = segment.coordinates
            guard Geo.polylinesIntersect(route, geometry, toleranceMetres: segmentToleranceMetres)
            else { continue }
            let entry = geometry
                .filter { Geo.distanceToPolyline($0, polyline: route) <= segmentToleranceMetres }
                .map { Geo.alongTrackDistance($0, polyline: route) }
                .min() ?? 0
            results.append(.mobile(check, alongTrackMetres: entry))
        }

        return results.sorted { $0.alongTrackMetres < $1.alongTrackMetres }
    }
}
