import Foundation

public enum Geo {
    static let earthRadiusMetres = 6_371_000.0

    public static func distance(_ a: Coordinate, _ b: Coordinate) -> Double {
        let lat1 = a.lat * .pi / 180, lat2 = b.lat * .pi / 180
        let dLat = (b.lat - a.lat) * .pi / 180
        let dLon = (b.lon - a.lon) * .pi / 180
        let h = sin(dLat / 2) * sin(dLat / 2)
            + cos(lat1) * cos(lat2) * sin(dLon / 2) * sin(dLon / 2)
        return 2 * earthRadiusMetres * asin(min(1, sqrt(h)))
    }

    public static func bearing(from a: Coordinate, to b: Coordinate) -> Double {
        let lat1 = a.lat * .pi / 180, lat2 = b.lat * .pi / 180
        let dLon = (b.lon - a.lon) * .pi / 180
        let y = sin(dLon) * cos(lat2)
        let x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dLon)
        let degrees = atan2(y, x) * 180 / .pi
        return degrees.truncatingRemainder(dividingBy: 360) < 0
            ? degrees + 360
            : degrees.truncatingRemainder(dividingBy: 360)
    }

    /// Smallest absolute difference between two bearings, 0...180.
    public static func angularDifference(_ a: Double, _ b: Double) -> Double {
        let raw = abs(a - b).truncatingRemainder(dividingBy: 360)
        return raw > 180 ? 360 - raw : raw
    }

    /// Perpendicular distance from a point to a segment, in metres, using a local
    /// equirectangular projection. Accurate well beyond the tolerances used here.
    static func distanceToSegment(_ p: Coordinate, _ a: Coordinate, _ b: Coordinate) -> Double {
        let latRad = a.lat * .pi / 180
        let mx = 111_320.0, my = 111_320.0 * cos(latRad)
        let px = (p.lon - a.lon) * my, py = (p.lat - a.lat) * mx
        let bx = (b.lon - a.lon) * my, by = (b.lat - a.lat) * mx
        let lengthSquared = bx * bx + by * by
        guard lengthSquared > 0 else { return distance(p, a) }
        let t = max(0, min(1, (px * bx + py * by) / lengthSquared))
        let dx = px - t * bx, dy = py - t * by
        return sqrt(dx * dx + dy * dy)
    }

    public static func distanceToPolyline(_ point: Coordinate, polyline: [Coordinate]) -> Double {
        guard polyline.count >= 2 else {
            return polyline.first.map { distance(point, $0) } ?? .infinity
        }
        var best = Double.infinity
        for i in 0..<(polyline.count - 1) {
            best = min(best, distanceToSegment(point, polyline[i], polyline[i + 1]))
        }
        return best
    }

    /// Distance travelled along the polyline to the projection of `point`.
    public static func alongTrackDistance(_ point: Coordinate, polyline: [Coordinate]) -> Double {
        guard polyline.count >= 2 else { return 0 }
        var travelled = 0.0
        var bestDistance = Double.infinity
        var bestAlong = 0.0
        for i in 0..<(polyline.count - 1) {
            let a = polyline[i], b = polyline[i + 1]
            let segmentLength = distance(a, b)
            let perpendicular = distanceToSegment(point, a, b)
            if perpendicular < bestDistance {
                bestDistance = perpendicular
                let projected = max(0, min(segmentLength, distance(a, point)))
                bestAlong = travelled + projected
            }
            travelled += segmentLength
        }
        return bestAlong
    }

    public static func polylinesIntersect(
        _ a: [Coordinate], _ b: [Coordinate], toleranceMetres: Double
    ) -> Bool {
        guard !a.isEmpty, !b.isEmpty else { return false }
        for point in b where distanceToPolyline(point, polyline: a) <= toleranceMetres {
            return true
        }
        for point in a where distanceToPolyline(point, polyline: b) <= toleranceMetres {
            return true
        }
        return false
    }
}
