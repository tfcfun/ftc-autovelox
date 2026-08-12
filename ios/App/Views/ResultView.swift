import SwiftUI
import MapKit
import VeloxKit

struct ResultView: View {
    @Environment(SnapshotProvider.self) private var provider
    let result: RouteResult

    var body: some View {
        VStack(spacing: 0) {
            if let days = provider.stalenessDays, days > 8 {
                Text(Copy.stalenessBanner(days: days))
                    .font(.footnote.weight(.medium))
                    .frame(maxWidth: .infinity)
                    .padding(8)
                    .background(.yellow.opacity(0.3))
            }

            resultMap
                .frame(height: 280)

            if result.findings.isEmpty {
                Spacer()
                Text(Copy.emptyState(publishedAt: provider.publishedAtDisplay))
                    .font(.body)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
                Spacer()
            } else {
                List(result.findings) { finding in
                    FindingRow(finding: finding, dateLabel: result.dateLabel)
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("Risultato")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Naviga", systemImage: "arrow.triangle.turn.up.right.diamond") {
                    openInMaps()
                }
            }
        }
    }

    @ViewBuilder
    private var resultMap: some View {
        Map {
            MapPolyline(coordinates: result.routeCoordinates)
                .stroke(.blue, lineWidth: 4)

            ForEach(matchedSegments, id: \.id) { segment in
                MapPolyline(coordinates: segment.coordinates.map {
                    CLLocationCoordinate2D(latitude: $0.lat, longitude: $0.lon)
                })
                .stroke(.orange, lineWidth: 6)
            }

            ForEach(fixedFindings, id: \.0.id) { camera, _ in
                if let coordinate = camera.coordinate {
                    Marker(camera.roadRef ?? camera.roadName,
                           systemImage: "camera.fill",
                           coordinate: CLLocationCoordinate2D(
                               latitude: coordinate.lat, longitude: coordinate.lon))
                    .tint(.red)
                }
            }
        }
    }

    private var fixedFindings: [(FixedCamera, Double)] {
        result.findings.compactMap {
            if case .fixed(let camera, let metres) = $0 { return (camera, metres) }
            return nil
        }
    }

    /// Road segments for the matched mobile checks, for the map highlight.
    private var matchedSegments: [RoadSegment] {
        guard let snapshot = provider.snapshot else { return [] }
        let segmentIds = Set(result.findings.compactMap { finding -> String? in
            if case .mobile(let check, _) = finding { return check.segmentId }
            return nil
        })
        return snapshot.roadSegments.filter { segmentIds.contains($0.id) }
    }

    private func openInMaps() {
        let placemark = MKPlacemark(coordinate: result.destinationCoordinate)
        let item = MKMapItem(placemark: placemark)
        item.name = result.destinationName
        item.openInMaps(launchOptions: [
            MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving
        ])
    }
}

struct FindingRow: View {
    let finding: Finding
    let dateLabel: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            switch finding {
            case .fixed(let camera, _):
                Label {
                    Text("\(camera.roadRef ?? camera.roadName) — postazione fissa")
                        .font(.headline)
                } icon: {
                    Image(systemName: "camera.fill").foregroundStyle(.red)
                }
                Text(fixedDetail(camera))
                    .font(.subheadline)
                    .foregroundStyle(Color(red: 0.2, green: 0.255, blue: 0.333))
            case .mobile(let check, _):
                Label {
                    Text("\(check.roadRef ?? check.roadName ?? "Strada") — controllo mobile")
                        .font(.headline)
                } icon: {
                    Image(systemName: "car.fill").foregroundStyle(.orange)
                }
                Text("\(check.roadType) · provincia \(check.province) · \(dateLabel)")
                    .font(.subheadline)
                    .foregroundStyle(Color(red: 0.2, green: 0.255, blue: 0.333))
            }
            Text(distanceText)
                .font(.footnote)
                .foregroundStyle(Color(red: 0.2, green: 0.255, blue: 0.333))
        }
        .padding(.vertical, 4)
    }

    private func fixedDetail(_ camera: FixedCamera) -> String {
        var parts: [String] = ["km \(camera.kmRaw)"]
        if let direction = camera.directionRaw { parts.append("dir. \(direction)") }
        parts.append("\(camera.comune) (\(camera.province))")
        return parts.joined(separator: " · ")
    }

    private var distanceText: String {
        let km = finding.alongTrackMetres / 1_000
        return String(format: "dopo %.1f km dall'inizio del percorso", km)
            .replacingOccurrences(of: ".", with: ",")
    }
}
