import SwiftUI
import VeloxKit

struct InfoView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Copertura") {
                    Text(Copy.coverageDisclaimer)
                        .font(.callout)
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
