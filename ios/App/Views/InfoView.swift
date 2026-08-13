import SwiftUI
import VeloxKit

struct InfoView: View {
    @Environment(SnapshotProvider.self) private var provider

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("FTC Autovelox")
                            .font(.headline)
                        Text(Copy.appPurpose)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 2)
                }

                Section("Copertura") {
                    Text(Copy.coverageDisclaimer)
                        .font(.callout)
                }
                Section("Dati caricati") {
                    LabeledContent("Elenco pubblicato il", value: provider.publishedAtDisplay)
                    if let week = provider.snapshot?.index.week {
                        LabeledContent("Settimana", value: week)
                    }
                    if let days = provider.stalenessDays, days > 8 {
                        Text(Copy.stalenessBanner(days: days))
                            .font(.footnote)
                    }
                }
                Section("Fonti") {
                    Link("Polizia di Stato — autovelox e tutor",
                         destination: URL(string: "https://www.poliziadistato.it/articolo/autovelox-e-tutor-dove-sono")!)
                    Link("MIT — elenco dispositivi",
                         destination: URL(string: "https://velox.mit.gov.it/dispositivi")!)
                }
            }
            .navigationTitle("Info")
        }
    }
}
