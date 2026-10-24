import SwiftUI

@main
struct VeloxApp: App {
    /// Launch-argument override (`-velox.tab region`) so automation can open a
    /// specific tab; defaults to the first tab for normal launches.
    @State private var selection: String =
        UserDefaults.standard.string(forKey: "velox.tab") ?? "route"

    @State private var snapshotProvider = SnapshotProvider()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            TabView(selection: $selection) {
                RouteView()
                    .tabItem { Label("Percorso", systemImage: "map") }
                    .tag("route")
                RegionView()
                    .tabItem { Label("Regione", systemImage: "list.bullet") }
                    .tag("region")
                FineCheckView()
                    .tabItem { Label("Multa", systemImage: "doc.text.magnifyingglass") }
                    .tag("multa")
                InfoView()
                    .tabItem { Label("Info", systemImage: "info.circle") }
                    .tag("info")
            }
            .environment(snapshotProvider)
            .task {
                snapshotProvider.loadCached()
                await snapshotProvider.refresh()
            }
            // `.task` runs once per process, and iOS keeps a suspended app alive
            // for weeks: on 2026-10-24 the phone still showed the 10/10 data
            // while Pages had published every day since. Refresh on every return
            // to the foreground as well.
            .onChange(of: scenePhase) { _, phase in
                if phase == .active {
                    Task { await snapshotProvider.refresh() }
                }
            }
        }
    }
}
