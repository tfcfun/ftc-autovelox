import SwiftUI
import MapKit
import UIKit
import VeloxKit

/// Live mode: warns on entering a monitored stretch, with no route planned.
///
/// Armed only by an explicit tap, and it says so on screen while running. The
/// whole country is in scope here, unlike trip mode, so `LiveMonitor` keeps the
/// proximity test strict and fires once per stretch.
struct LiveView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(SnapshotProvider.self) private var provider

    @State private var locationService = LocationService()
    @State private var announcer = Announcer()
    @State private var monitor: LiveMonitor?
    @State private var lastAlert: VeloxKit.Alert?
    @State private var camera: MapCameraPosition = .userLocation(fallback: .automatic)
    @State private var hasFix = false

    var body: some View {
        VStack(spacing: 16) {
            Text(Copy.liveModeArmed)
                .font(.title2.weight(.semibold))
                .padding(.top, 20)

            liveMap
                .frame(maxWidth: .infinity)
                .frame(height: 300)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal)

            if let alert = lastAlert {
                Text(alert.message)
                    .font(.title3.weight(.medium))
                    .multilineTextAlignment(.center)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(.orange.opacity(0.25), in: RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal)
            } else if hasFix {
                Text(Copy.liveModeIdle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else {
                Text("In attesa del segnale GPS…")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button(role: .destructive) {
                stop()
            } label: {
                Text("Ferma modalità live")
                    .font(.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .padding([.horizontal, .bottom], 16)
        }
        .onAppear { start() }
        .onDisappear { locationService.stop(); UIApplication.shared.isIdleTimerDisabled = false }
        .onChange(of: locationService.latestFix) { _, fix in
            guard let fix else { return }
            hasFix = true
            monitor?.setDate(Self.today())
            if let alert = monitor?.consume(fix) {
                lastAlert = alert
                announcer.speak(alert.message)
            }
        }
    }

    @ViewBuilder
    private var liveMap: some View {
        Map(position: $camera) {
            UserAnnotation()

            ForEach(nearbyStretches, id: \.id) { item in
                MapPolyline(coordinates: item.coordinates.map {
                    CLLocationCoordinate2D(latitude: $0.lat, longitude: $0.lon)
                })
                .stroke(.red.opacity(0.55), lineWidth: 8)
            }

            ForEach(todaysSegments, id: \.id) { segment in
                MapPolyline(coordinates: segment.coordinates.map {
                    CLLocationCoordinate2D(latitude: $0.lat, longitude: $0.lon)
                })
                .stroke(.orange, lineWidth: 7)
            }
        }
        .mapControls {
            MapUserLocationButton()
            MapCompass()
        }
    }

    /// Fixed-camera stretches near the current position.
    ///
    /// Drawing all 54 nationally would be a wall of colour and would cost
    /// rendering time for roads hundreds of kilometres away.
    private var nearbyStretches: [(id: String, coordinates: [Coordinate])] {
        guard let here = locationService.latestFix?.coordinate,
              let snapshot = provider.snapshot else { return [] }
        return snapshot.fixedCameras.flatMap { camera in
            camera.uncertaintyStretches.enumerated().compactMap { index, stretch in
                guard let first = stretch.first,
                      Geo.distance(here, first) < 30_000 else { return nil }
                return (id: "\(camera.id)-\(index)", coordinates: stretch)
            }
        }
    }

    private var todaysSegments: [RoadSegment] {
        guard let snapshot = provider.snapshot else { return [] }
        let today = Self.today()
        let ids = Set(snapshot.mobileChecks
            .filter { $0.date == today }
            .compactMap(\.segmentId))
        return snapshot.roadSegments.filter { ids.contains($0.id) }
    }

    private static func today() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.timeZone = TimeZone(identifier: "Europe/Rome")
        return formatter.string(from: Date())
    }

    private func start() {
        guard let snapshot = provider.snapshot else { return }
        monitor = LiveMonitor(snapshot: snapshot, date: Self.today())
        locationService.start()
        UIApplication.shared.isIdleTimerDisabled = true
    }

    private func stop() {
        locationService.stop()
        UIApplication.shared.isIdleTimerDisabled = false
        dismiss()
    }
}
