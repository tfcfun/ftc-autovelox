import Foundation

public enum MITSearch {
    private static func fold(_ text: String) -> String {
        text.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
            .replacingOccurrences(of: "\"", with: " ")
            .replacingOccurrences(of: "'", with: " ")
    }

    /// All query terms must match somewhere in the record. An empty query matches
    /// nothing — showing 4,110 devices to someone who typed nothing is not a result.
    public static func search(
        _ query: String, in devices: [MITDevice], limit: Int = 50
    ) -> [MITDevice] {
        let terms = fold(query).split(whereSeparator: { $0 == " " }).map(String.init)
        guard !terms.isEmpty else { return [] }

        var matches: [MITDevice] = []
        for device in devices {
            let haystack = fold(
                [device.ente, device.marca, device.modello, device.versione,
                 device.matricola, device.codiceAccertatore, device.nDecreto]
                    .joined(separator: " ")
            )
            if terms.allSatisfy({ haystack.contains($0) }) {
                matches.append(device)
                if matches.count >= limit { break }
            }
        }
        return matches
    }
}
