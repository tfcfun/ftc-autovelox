import SwiftUI
import VeloxKit

/// Search the MIT register for the device named on a verbale.
///
/// This screen reports whether a device appears in the official register. It
/// deliberately stops there: it does not tell the user a fine is valid or
/// invalid, because that is a legal conclusion this app is in no position to
/// draw. Absence in the register can also mean the ente simply filed it under a
/// different serial.
struct FineCheckView: View {
    @Environment(SnapshotProvider.self) private var provider

    @State private var query: String = ""

    private var results: [MITDevice] {
        MITSearch.search(query, in: provider.snapshot?.mitDevices ?? [])
    }

    private var deviceCount: Int { provider.snapshot?.mitDevices.count ?? 0 }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(Copy.mitRegisterExplainer(deviceCount: deviceCount))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                if query.trimmingCharacters(in: .whitespaces).isEmpty {
                    Section {
                        Text(Copy.mitSearchPrompt)
                            .font(.callout)
                    }
                } else if results.isEmpty {
                    Section {
                        // Not "this fine is invalid" - only what we can actually say.
                        Text(Copy.mitNoMatch)
                            .font(.callout)
                    }
                } else {
                    Section("\(results.count) dispositivi") {
                        ForEach(results) { device in
                            VStack(alignment: .leading, spacing: 3) {
                                Text("\(device.marca) \(device.modello)")
                                    .font(.body)
                                Text(device.ente)
                                    .font(.footnote)
                                    .foregroundStyle(.secondary)
                                Text(Self.detail(device))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            .searchable(
                text: $query,
                prompt: "Ente, marca, modello o matricola"
            )
            .navigationTitle("Controlla la multa")
        }
    }

    private static func detail(_ device: MITDevice) -> String {
        var parts: [String] = []
        if !device.matricola.isEmpty { parts.append("matr. \(device.matricola)") }
        if !device.nDecreto.isEmpty { parts.append("decreto \(device.nDecreto)") }
        if let decree = device.dataDecreto { parts.append(Self.italianDate(decree)) }
        if device.tipo != "sconosciuto" { parts.append(device.tipo) }
        return parts.joined(separator: " · ")
    }

    private static func italianDate(_ iso: String) -> String {
        let input = DateFormatter()
        input.dateFormat = "yyyy-MM-dd"
        guard let date = input.date(from: iso) else { return iso }
        let output = DateFormatter()
        output.dateFormat = "dd/MM/yy"
        return output.string(from: date)
    }
}
