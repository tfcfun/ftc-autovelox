import SwiftUI
import MapKit
import CoreLocation
import VeloxKit

/// The output of one route calculation, pushed to `ResultView`.
struct RouteResult: Hashable, Identifiable {
    let id = UUID()
    let routeCoordinates: [CLLocationCoordinate2D]
    let route: [Coordinate]
    let findings: [Finding]
    let destinationName: String
    let destinationCoordinate: CLLocationCoordinate2D
    let dateLabel: String

    static func == (lhs: RouteResult, rhs: RouteResult) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

struct RouteView: View {
    @Environment(SnapshotProvider.self) private var provider

    @State private var origin = ""
    @State private var destination = ""
    @State private var date = Date()
    @State private var isCalculating = false
    @State private var errorText: String?
    @State private var result: RouteResult?
    /// Debug-only: set by the `-velox.demoTrip` launch argument so trip mode can
    /// be exercised in the simulator without typing addresses. Not user-reachable.
    @State private var demoTripResult: RouteResult?
    @State private var currentPlace = CurrentPlace()

    var body: some View {
        NavigationStack {
            Form {
                Section("Percorso") {
                    TextField("Partenza", text: $origin)
                        .textInputAutocapitalization(.words)
                    // Explicit tap only. The app never reaches for the GPS by itself.
                    Button {
                        Task { await useCurrentPosition() }
                    } label: {
                        HStack(spacing: 6) {
                            if currentPlace.isResolving {
                                ProgressView().controlSize(.small)
                            } else {
                                Image(systemName: "location.fill")
                            }
                            Text("Usa la mia posizione")
                        }
                        .font(.callout)
                    }
                    .disabled(currentPlace.isResolving)
                    TextField("Arrivo", text: $destination)
                        .textInputAutocapitalization(.words)
                    DatePicker("Giorno", selection: $date, in: dateRange,
                               displayedComponents: .date)
                        .environment(\.locale, Locale(identifier: "it_IT"))
                }
                Section {
                    Button {
                        Task { await calculate() }
                    } label: {
                        if isCalculating {
                            ProgressView()
                        } else {
                            Text("Calcola")
                        }
                    }
                    .disabled(origin.trimmingCharacters(in: .whitespaces).isEmpty
                              || destination.trimmingCharacters(in: .whitespaces).isEmpty
                              || isCalculating
                              || provider.snapshot == nil)
                    if let errorText {
                        Text(errorText).foregroundStyle(.red).font(.callout)
                    }
                }
                if let note = provider.freshnessNote {
                    Section {
                        Text(note).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Percorso")
            .navigationDestination(item: $result) { result in
                ResultView(result: result)
            }
            .fullScreenCover(item: $demoTripResult) { demo in
                TripView(result: demo)
            }
            .task { await presentDemoTripIfRequested() }
        }
    }

    /// Debug-only trip along the seed SS9 segment, driven by `simctl location`.
    private func presentDemoTripIfRequested() async {
        guard UserDefaults.standard.bool(forKey: "velox.demoTrip") else { return }
        while provider.snapshot == nil {
            try? await Task.sleep(for: .milliseconds(100))
        }
        guard let snapshot = provider.snapshot,
              let segment = snapshot.roadSegments.first else { return }
        let route = segment.coordinates
        let findings = RouteMatcher.findings(
            route: route, snapshot: snapshot, date: "2026-08-14")
        demoTripResult = RouteResult(
            routeCoordinates: route.map {
                CLLocationCoordinate2D(latitude: $0.lat, longitude: $0.lon)
            },
            route: route,
            findings: findings,
            destinationName: "Demo",
            destinationCoordinate: CLLocationCoordinate2D(
                latitude: route.last?.lat ?? 0, longitude: route.last?.lon ?? 0),
            dateLabel: "venerdì 14/08/26"
        )
    }

    /// The selectable days: the published snapshot week when known.
    private var dateRange: ClosedRange<Date> {
        if let week = provider.snapshot?.index.week,
           let range = Self.weekRange(week),
           range.contains(date) || date < range.upperBound {
            return range
        }
        return Date()...Date().addingTimeInterval(6 * 86_400)
    }

    static func weekRange(_ week: String) -> ClosedRange<Date>? {
        let parts = week.split(separator: "-W")
        guard parts.count == 2, let year = Int(parts[0]), let weekOfYear = Int(parts[1])
        else { return nil }
        var calendar = Calendar(identifier: .iso8601)
        calendar.timeZone = .current
        let components = DateComponents(weekOfYear: weekOfYear, yearForWeekOfYear: year)
        guard let start = calendar.date(from: components) else { return nil }
        return start...start.addingTimeInterval(7 * 86_400 - 1)
    }

    /// Fill Partenza from the device's current position.
    ///
    /// Resolves to a place name rather than raw coordinates so the user can see
    /// what the app thinks it found, and type over it if it guessed the wrong town.
    private func useCurrentPosition() async {
        errorText = nil
        do {
            origin = try await currentPlace.resolveName()
        } catch {
            errorText = (error as? LocalizedError)?.errorDescription
                ?? "Posizione non disponibile."
        }
    }

    private func calculate() async {
        guard let snapshot = provider.snapshot else { return }
        isCalculating = true
        defer { isCalculating = false }
        errorText = nil
        do {
            let geocoder = CLGeocoder()
            guard let originLocation = try await geocoder
                .geocodeAddressString(origin).first?.location else {
                throw CLError(.geocodeFoundNoResult)
            }
            guard let destinationPlacemark = try await geocoder
                .geocodeAddressString(destination).first,
                let destinationLocation = destinationPlacemark.location else {
                throw CLError(.geocodeFoundNoResult)
            }

            let request = MKDirections.Request()
            request.source = MKMapItem(placemark: MKPlacemark(
                coordinate: originLocation.coordinate))
            request.destination = MKMapItem(placemark: MKPlacemark(
                coordinate: destinationLocation.coordinate))
            request.transportType = .automobile
            let response = try await MKDirections(request: request).calculate()
            guard let mkRoute = response.routes.first else {
                throw MKError(.directionsNotFound)
            }

            let clCoordinates = mkRoute.polyline.coordinateArray
            let route = clCoordinates.map { Coordinate(lat: $0.latitude, lon: $0.longitude) }

            let dayFormatter = DateFormatter()
            dayFormatter.locale = Locale(identifier: "en_US_POSIX")
            dayFormatter.dateFormat = "yyyy-MM-dd"
            let dateString = dayFormatter.string(from: date)

            let labelFormatter = DateFormatter()
            labelFormatter.locale = Locale(identifier: "it_IT")
            labelFormatter.dateFormat = "EEEE dd/MM/yy"

            result = RouteResult(
                routeCoordinates: clCoordinates,
                route: route,
                findings: RouteMatcher.findings(
                    route: route, snapshot: snapshot, date: dateString),
                destinationName: destination,
                destinationCoordinate: destinationLocation.coordinate,
                dateLabel: labelFormatter.string(from: date)
            )
        } catch {
            errorText = "Percorso non calcolabile. Controlla gli indirizzi e la connessione."
        }
    }
}

extension MKPolyline {
    /// The polyline's points as plain coordinates.
    var coordinateArray: [CLLocationCoordinate2D] {
        var coordinates = [CLLocationCoordinate2D](
            repeating: kCLLocationCoordinate2DInvalid, count: pointCount)
        getCoordinates(&coordinates, range: NSRange(location: 0, length: pointCount))
        return coordinates
    }
}
