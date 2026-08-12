import SwiftUI

@main
struct VeloxApp: App {
    /// Launch-argument override (`-velox.tab region`) so automation can open a
    /// specific tab; defaults to the first tab for normal launches.
    @State private var selection: String =
        UserDefaults.standard.string(forKey: "velox.tab") ?? "route"

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
        }
    }
}
