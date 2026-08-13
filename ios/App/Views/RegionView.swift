import SwiftUI
import VeloxKit

/// Browse the published week one region at a time.
///
/// The dataset is small enough to read whole, which makes this the screen where
/// a user can see for themselves what the Polizia Stradale actually published.
/// It therefore has to be honest about the difference between a region that
/// published a zero and one whose feed we could not read: `empty` is
/// information, `stale` and `failed` are our ignorance, and they must never
/// look the same.
struct RegionView: View {
    @Environment(SnapshotProvider.self) private var provider

    @State private var region: String = "Lombardia"

    private static let regions = [
        "Abruzzo", "Basilicata", "Calabria", "Campania", "Emilia", "Friuli",
        "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte",
        "Puglia", "Sardegna", "Sicilia", "Toscana", "Trentino", "Umbria",
        "Valle d'Aosta", "Veneto",
    ]

    private var status: RegionStatus? { provider.snapshot?.index.regions[region] }

    private var checks: [MobileCheck] {
        (provider.snapshot?.mobileChecks ?? [])
            .filter { $0.region == region }
            .sorted { ($0.date, $0.roadRef ?? "") < ($1.date, $1.roadRef ?? "") }
    }

    private var cameras: [FixedCamera] {
        (provider.snapshot?.fixedCameras ?? [])
            .filter { $0.region == region }
            .sorted { $0.roadName < $1.roadName }
    }

    var body: some View {
        NavigationStack {
            List {
                Picker("Regione", selection: $region) {
                    ForEach(Self.regions, id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.menu)

                if let days = provider.stalenessDays, days > 8 {
                    Text(Copy.stalenessBanner(days: days))
                        .font(.footnote)
                        .foregroundStyle(.orange)
                }

                weeklySection
                fixedSection
            }
            .navigationTitle("Regione")
        }
    }

    @ViewBuilder
    private var weeklySection: some View {
        Section("Controlli mobili della settimana") {
            switch status?.status {
            case "ok":
                ForEach(checks) { check in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(check.roadRef ?? check.roadName ?? "—") · \(check.province)")
                            .font(.body)
                        Text("\(Self.dayLabel(check.date)) · \(check.roadType)")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            case "empty":
                // The region published a zero. That is a fact, not a gap.
                Text(Copy.emptyState(publishedAt: provider.publishedAtDisplay))
                    .font(.callout)
            case "stale", "failed", .some, .none:
                // We do not know. Never render this as an all-clear.
                Text(Copy.regionUnavailable(region: region))
                    .font(.callout)
                    .foregroundStyle(.orange)
            }
        }
    }

    @ViewBuilder
    private var fixedSection: some View {
        Section("Postazioni fisse") {
            if cameras.isEmpty {
                Text(Copy.noFixedInstallations)
                    .font(.callout)
            } else {
                ForEach(cameras) { camera in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(camera.roadName) · km \(camera.kmRaw)")
                        Text(Self.cameraDetail(camera))
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private static func cameraDetail(_ camera: FixedCamera) -> String {
        var parts = ["\(camera.comune) (\(camera.province))"]
        if let direction = camera.directionRaw { parts.append("dir. \(direction)") }
        if !camera.isTrustworthyForProximityAlerts {
            // Say so rather than implying a precision we do not have.
            parts.append("posizione approssimativa")
        }
        return parts.joined(separator: " · ")
    }

    /// dd/MM/yy, per house style.
    private static func dayLabel(_ iso: String) -> String {
        let input = DateFormatter()
        input.dateFormat = "yyyy-MM-dd"
        input.locale = Locale(identifier: "it_IT")
        guard let date = input.date(from: iso) else { return iso }
        let output = DateFormatter()
        output.locale = Locale(identifier: "it_IT")
        output.dateFormat = "EEEE dd/MM/yy"
        return output.string(from: date).capitalized
    }
}
