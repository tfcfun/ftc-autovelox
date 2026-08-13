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

public extension Copy {
    /// A region whose feed we could not read. Distinct from a published zero.
    static func regionUnavailable(region: String) -> String {
        """
        Dati non disponibili per \(region) in questa settimana. \
        Non è possibile sapere quali controlli siano previsti.
        """
    }

    /// Shown when a region has no fixed installations in the published list.
    /// Qualified, because the app only ever knows about Polizia Stradale ones.
    static let noFixedInstallations = """
        Nessuna postazione fissa della Polizia Stradale in questa regione. \
        Gli autovelox comunali non sono inclusi in questo elenco.
        """

    static func mitRegisterExplainer(deviceCount: Int) -> String {
        """
        Il MIT pubblica l'elenco dei dispositivi di rilevamento della velocità \
        censiti: \(deviceCount) al momento dell'ultimo aggiornamento. \
        Dal 28 novembre 2025 solo i dispositivi censiti possono elevare sanzioni.
        """
    }

    static let mitSearchPrompt = """
        Cerca il dispositivo indicato sul verbale, per ente, marca, modello o \
        numero di matricola.
        """

    /// Deliberately reports only what was searched, never a legal conclusion.
    static let mitNoMatch = """
        Nessun dispositivo corrispondente nell'elenco del MIT. \
        Questo non significa che la sanzione sia invalida: verifica i dati \
        trascritti dal verbale, l'ente potrebbe averlo registrato diversamente.
        """
}

public extension Copy {
    /// Entering a stretch where a fixed installation is known to be.
    ///
    /// Deliberately states no distance. The sources do not say where along the
    /// stretch the camera stands, and inventing "tra 800 metri" would be a
    /// number we made up.
    static func stretchEntryAlert(road: String) -> String {
        "Tratto con controllo velocità su \(road) — rispetta il limite."
    }
}
