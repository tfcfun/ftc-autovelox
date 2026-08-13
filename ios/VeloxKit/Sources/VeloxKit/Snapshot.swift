import Foundation

public struct Coordinate: Equatable, Sendable {
    public let lat: Double
    public let lon: Double
    public init(lat: Double, lon: Double) { self.lat = lat; self.lon = lon }
}

public enum SnapshotError: Error, Equatable {
    case unsupportedSchema(Int)
    case malformed(String)
}

public struct RegionStatus: Codable, Equatable, Sendable {
    public let status: String
    public let updatedAt: String
    public let rows: Int
    public let quarantined: Int

    enum CodingKeys: String, CodingKey {
        case status, rows, quarantined
        case updatedAt = "updated_at"
    }
}

public struct SnapshotIndex: Codable, Equatable, Sendable {
    public let schemaVersion: Int
    public let generatedAt: String
    public let week: String
    public let regions: [String: RegionStatus]
    public let quarantineCount: Int

    enum CodingKeys: String, CodingKey {
        case week, regions
        case schemaVersion = "schema_version"
        case generatedAt = "generated_at"
        case quarantineCount = "quarantine_count"
    }

    public static let supportedSchemaVersion = 1

    public static func decode(from data: Data) throws -> SnapshotIndex {
        let index = try JSONDecoder().decode(SnapshotIndex.self, from: data)
        guard index.schemaVersion == supportedSchemaVersion else {
            throw SnapshotError.unsupportedSchema(index.schemaVersion)
        }
        return index
    }

    /// Days between `generatedAt` and `now`. Used for the staleness banner.
    public func ageInDays(now: Date = Date()) -> Int? {
        let formatter = ISO8601DateFormatter()
        guard let generated = formatter.date(from: generatedAt) else { return nil }
        return Calendar(identifier: .gregorian)
            .dateComponents([.day], from: generated, to: now).day
    }
}

public struct FixedCamera: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let network: String
    public let region: String
    public let roadName: String
    public let roadRef: String?
    public let kmRaw: String
    public let km: Double?
    public let directionRaw: String?
    public let bearingDeg: Int?
    public let comune: String
    public let province: String
    public let lat: Double?
    public let lon: Double?
    public let geocodeConfidence: String
    public let verified: Bool

    enum CodingKeys: String, CodingKey {
        case id, network, region, comune, province, lat, lon, km, verified
        case roadName = "road_name"
        case roadRef = "road_ref"
        case kmRaw = "km_raw"
        case directionRaw = "direction_raw"
        case bearingDeg = "bearing_deg"
        case geocodeConfidence = "geocode_confidence"
    }

    /// nil when the camera could not be placed. Never substitutes 0,0.
    public var coordinate: Coordinate? {
        guard let lat, let lon else { return nil }
        return Coordinate(lat: lat, lon: lon)
    }
}

public struct MobileCheck: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let date: String
    public let week: String
    public let region: String
    public let roadType: String
    public let roadRef: String?
    public let roadName: String?
    public let province: String
    public let segmentId: String?

    enum CodingKeys: String, CodingKey {
        case id, date, week, region, province
        case roadType = "road_type"
        case roadRef = "road_ref"
        case roadName = "road_name"
        case segmentId = "segment_id"
    }
}

public struct RoadSegment: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let roadRef: String
    public let province: String
    public let geometry: [[Double]]

    enum CodingKeys: String, CodingKey {
        case id, province, geometry
        case roadRef = "road_ref"
    }

    /// Geometry is stored [lon, lat]; expose it in the app's coordinate order.
    public var coordinates: [Coordinate] {
        geometry.compactMap { pair in
            pair.count == 2 ? Coordinate(lat: pair[1], lon: pair[0]) : nil
        }
    }
}

public struct MITDevice: Codable, Equatable, Identifiable, Sendable {
    public let id: Int
    public let ente: String
    public let codiceAccertatore: String
    public let codiceCatastale: String
    public let tipo: String
    public let tipoRaw: String
    public let marca: String
    public let modello: String
    public let versione: String
    public let matricola: String
    public let nDecreto: String
    public let dataDecreto: String?

    enum CodingKeys: String, CodingKey {
        case id, ente, tipo, marca, modello, versione, matricola
        case codiceAccertatore = "codice_accertatore"
        case codiceCatastale = "codice_catastale"
        case tipoRaw = "tipo_raw"
        case nDecreto = "n_decreto"
        case dataDecreto = "data_decreto"
    }
}

public struct Snapshot: Equatable, Sendable {
    public let index: SnapshotIndex
    public let fixedCameras: [FixedCamera]
    public let mobileChecks: [MobileCheck]
    public let roadSegments: [RoadSegment]
    public let mitDevices: [MITDevice]

    public static func load(from directory: URL) throws -> Snapshot {
        func read<T: Decodable>(_ name: String, as type: T.Type) throws -> T {
            let url = directory.appendingPathComponent(name)
            guard let data = try? Data(contentsOf: url) else {
                throw SnapshotError.malformed("missing \(name)")
            }
            return try JSONDecoder().decode(T.self, from: data)
        }

        let indexData = try Data(contentsOf: directory.appendingPathComponent("index.json"))
        return Snapshot(
            index: try SnapshotIndex.decode(from: indexData),
            fixedCameras: try read("fixed_cameras.json", as: [FixedCamera].self),
            mobileChecks: try read("mobile_checks.json", as: [MobileCheck].self),
            roadSegments: try read("road_segments.json", as: [RoadSegment].self),
            mitDevices: try read("mit_devices.json", as: [MITDevice].self)
        )
    }
}

public extension FixedCamera {
    /// Whether this camera's position is good enough to warn a moving driver.
    ///
    /// Only two things earn that: a human confirmed the point during the review
    /// pass, or the pipeline placed it by interpolating a real kilometre marker
    /// along known road geometry. Comune-derived placement is roughly 1-2 km out
    /// and is map-only.
    var isTrustworthyForProximityAlerts: Bool {
        verified || geocodeConfidence == "high"
    }
}
