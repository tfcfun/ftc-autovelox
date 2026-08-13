import SwiftUI
import UIKit
import VeloxKit

/// Trip mode: armed only by the explicit tap that presented this screen.
struct TripView: View {
    @Environment(\.dismiss) private var dismiss
    let result: RouteResult

    @State private var locationService = LocationService()
    @State private var engine: AlertEngine?
    @State private var announcer = Announcer()
    @State private var lastAlert: VeloxKit.Alert?
    @State private var progressMetres: Double = 0
    @State private var hasFix = false

    var body: some View {
        VStack(spacing: 24) {
            Text("Modalità viaggio attiva")
                .font(.title2.weight(.semibold))
                .padding(.top, 32)

            if let alert = lastAlert {
                Text(alert.message)
                    .font(.title3.weight(.medium))
                    .multilineTextAlignment(.center)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(.orange.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal)
            }

            Spacer()

            if let next = nextFinding {
                VStack(spacing: 8) {
                    Text("Prossimo controllo")
                        .font(.headline)
                    Text(title(for: next))
                        .font(.title3)
                        .multilineTextAlignment(.center)
                    Text(remainingText(for: next))
                        .font(.system(size: 44, weight: .bold, design: .rounded))
                        .monospacedDigit()
                }
                .padding(.horizontal)
            } else {
                Text(Copy.emptyState(publishedAt: publishedAt))
                    .font(.body)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
            }

            if !hasFix {
                Text("In attesa del segnale GPS…")
                    .font(.footnote)
                    .foregroundStyle(Color(red: 0.2, green: 0.255, blue: 0.333))
            }

            Spacer()

            Button {
                endTrip()
            } label: {
                Text("Termina viaggio")
                    .font(.title3.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            }
            .buttonStyle(.borderedProminent)
            .tint(.red)
            .padding([.horizontal, .bottom], 24)
        }
        .onAppear {
            UIApplication.shared.isIdleTimerDisabled = true
            engine = AlertEngine(findings: result.findings, route: result.route)
            locationService.start()
        }
        .onDisappear {
            UIApplication.shared.isIdleTimerDisabled = false
            locationService.stop()
        }
        .onChange(of: locationService.latestFix) { _, fix in
            guard let fix else { return }
            hasFix = true
            progressMetres = Geo.alongTrackDistance(fix.coordinate, polyline: result.route)
            if let alert = engine?.consume(fix) {
                lastAlert = alert
                announcer.speak(alert.message)
            }
        }
    }

    @Environment(SnapshotProvider.self) private var provider
    private var publishedAt: String { provider.publishedAtDisplay }

    /// The first finding still ahead of the vehicle.
    private var nextFinding: Finding? {
        result.findings.first { $0.alongTrackMetres > progressMetres }
    }

    private func title(for finding: Finding) -> String {
        switch finding {
        case .fixed(let camera, _):
            return "\(camera.roadRef ?? camera.roadName) — postazione fissa"
        case .mobile(let check, _):
            return "\(check.roadRef ?? check.roadName ?? "Strada") — controllo mobile (\(check.province))"
        }
    }

    private func remainingText(for finding: Finding) -> String {
        let remaining = max(0, finding.alongTrackMetres - progressMetres)
        if remaining >= 1_000 {
            return String(format: "%.1f km", remaining / 1_000)
                .replacingOccurrences(of: ".", with: ",")
        }
        return "\(Int(remaining.rounded())) m"
    }

    private func endTrip() {
        locationService.stop()
        UIApplication.shared.isIdleTimerDisabled = false
        dismiss()
    }
}
