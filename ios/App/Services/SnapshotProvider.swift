import Foundation
import VeloxKit

/// Loads the snapshot the whole app reads.
///
/// Order of truth: cached download in Application Support, else the seed
/// bundled with the app. A failed refresh keeps the previous snapshot and
/// surfaces the error; it never falls back to an empty snapshot, because an
/// empty snapshot renders as an all-clear.
@MainActor
@Observable
final class SnapshotProvider {
    private(set) var snapshot: Snapshot?
    private(set) var errorMessage: String?
    private(set) var didRefreshFail = false

    private let remoteBase = URL(string:
        "https://tfcfun.github.io/ftc-autovelox/data/latest/")!

    private var cacheDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory,
                                            in: .userDomainMask)[0]
        return base.appendingPathComponent("snapshot", isDirectory: true)
    }

    var stalenessDays: Int? { snapshot?.index.ageInDays() }

    /// Whether what the user is looking at is still good, regardless of whether
    /// the last refresh attempt succeeded.
    var isDataCurrent: Bool {
        guard let days = stalenessDays else { return snapshot != nil }
        return days <= 8
    }

    /// The one line the user sees about data freshness.
    ///
    /// Always carries the publication date, because that is what actually tells
    /// them whether to trust the screen. A failed refresh over current data is a
    /// statement of fact, not a warning.
    var freshnessNote: String? {
        guard let snapshot else { return nil }
        if didRefreshFail && !isDataCurrent {
            return Copy.refreshFailed(publishedAt: publishedAtDisplay)
        }
        if let coverage = snapshot.index.coverage {
            let short = DateFormatter()
            short.locale = Locale(identifier: "it_IT")
            short.dateFormat = "dd/MM"
            return Copy.dataCoverage(from: short.string(from: coverage.from),
                                     to: short.string(from: coverage.to),
                                     publishedAt: publishedAtDisplay)
        }
        return Copy.dataAsOf(publishedAt: publishedAtDisplay)
    }

    /// The days the published programme covers, for bounding the date picker.
    var coverageRange: ClosedRange<Date>? {
        guard let c = snapshot?.index.coverage, c.from <= c.to else { return nil }
        return c.from...c.to
    }

    /// The snapshot's publication date, formatted dd/MM/yyyy for display.
    var publishedAtDisplay: String {
        guard let generatedAt = snapshot?.index.generatedAt,
              let date = ISO8601DateFormatter().date(from: generatedAt) else {
            return snapshot?.index.generatedAt ?? "—"
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "it_IT")
        formatter.dateFormat = "dd/MM/yyyy"
        return formatter.string(from: date)
    }

    func loadCached() {
        if FileManager.default.fileExists(atPath: cacheDirectory.path),
           let cached = try? Snapshot.load(from: cacheDirectory) {
            snapshot = cached
            return
        }
        // First run, or unreadable cache: fall back to the bundled seed.
        if let seed = Bundle.main.url(forResource: "seed", withExtension: nil),
           let bundled = try? Snapshot.load(from: seed) {
            snapshot = bundled
        }
    }

    func refresh() async {
        let names = ["index.json", "fixed_cameras.json", "mobile_checks.json",
                     "road_segments.json", "mit_devices.json", "quarantine.json"]
        let staging = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: staging, withIntermediateDirectories: true)
            for name in names {
                let (data, response) = try await URLSession.shared.data(
                    from: remoteBase.appending(path: name))
                if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                    throw URLError(.badServerResponse)
                }
                try data.write(to: staging.appendingPathComponent(name))
            }
            let candidate = try Snapshot.load(from: staging)  // validate before adopting
            try? FileManager.default.removeItem(at: cacheDirectory)
            try FileManager.default.createDirectory(
                at: cacheDirectory.deletingLastPathComponent(),
                withIntermediateDirectories: true)
            try FileManager.default.moveItem(at: staging, to: cacheDirectory)
            snapshot = candidate
            errorMessage = nil
            didRefreshFail = false
        } catch {
            // The previously loaded snapshot is retained deliberately, and a
            // failed refresh is only worth mentioning when the data the user is
            // actually looking at has gone stale. Saying "update failed" while
            // showing a current week reads as breakage when nothing is broken.
            didRefreshFail = true
        }
    }
}
