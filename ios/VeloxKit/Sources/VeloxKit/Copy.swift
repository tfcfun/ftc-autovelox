import Foundation

/// Every user-facing sentence that makes a claim about enforcement.
///
/// The app knows only what the Polizia Stradale publishes. It therefore cannot
/// say a road is clear — only that nothing is published for a date. `CopyTests`
/// asserts that no string here breaks that rule.
public enum Copy {
    public static let forbiddenPhrases = [
        "nessun autovelox",
        "strada libera",
        "nessun controllo attivo",
        "puoi correre",
        "via libera",
    ]

    public static func fixedCameraAlert(metres: Int) -> String {
        "Controllo velocità tra \(metres) metri — rispetta il limite."
    }

    public static func scheduledRoadAlert(road: String, province: String) -> String {
        "Su \(road) (\(province)) è previsto oggi un controllo della velocità — rispetta il limite."
    }

    public static func emptyState(publishedAt: String) -> String {
        """
        Nessun controllo della Polizia Stradale pubblicato per questa data.
        Elenco pubblicato il \(publishedAt).
        """
    }

    public static let coverageDisclaimer = """
        Questa app mostra solo i controlli pubblicati dalla Polizia Stradale. \
        Gli autovelox gestiti dai comuni e dalle polizie locali non sono inclusi: \
        non esiste un elenco ufficiale con le loro posizioni.
        """

    public static func stalenessBanner(days: Int) -> String {
        "Dati non aggiornati da \(days) giorni. Controlla la connessione."
    }
}
