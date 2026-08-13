import CoreLocation
import Foundation

/// A one-shot "where am I" lookup for the Partenza field.
///
/// Deliberately separate from `LocationService`, which is the trip-mode engine:
/// this asks once, reverse-geocodes, and stops. Nothing here keeps the GPS on,
/// and the authorisation prompt only ever appears because the user tapped the
/// button — the app never asks for location on its own.
@MainActor
@Observable
final class CurrentPlace: NSObject, CLLocationManagerDelegate {
    enum Failure: LocalizedError {
        case denied
        case unavailable

        var errorDescription: String? {
            switch self {
            case .denied:
                return "Accesso alla posizione negato. Puoi attivarlo in Impostazioni."
            case .unavailable:
                return "Posizione non disponibile in questo momento."
            }
        }
    }

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocation, Error>?

    private(set) var isResolving = false

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    /// A human-readable place name for the current position, e.g. "Milano".
    ///
    /// Returns a name rather than coordinates so the field stays legible and the
    /// user can see, and correct, what the app thinks it resolved.
    func resolveName() async throws -> String {
        isResolving = true
        defer { isResolving = false }

        let location = try await requestLocation()
        let placemarks = try? await CLGeocoder().reverseGeocodeLocation(location)
        guard let placemark = placemarks?.first else {
            // Fall back to coordinates rather than failing: a usable origin beats
            // a pretty one, and the user can always type over it.
            return String(format: "%.5f, %.5f",
                          location.coordinate.latitude, location.coordinate.longitude)
        }
        let parts = [placemark.locality, placemark.subAdministrativeArea]
            .compactMap { $0 }
        return parts.first ?? placemark.name ?? String(
            format: "%.5f, %.5f",
            location.coordinate.latitude, location.coordinate.longitude
        )
    }

    private func requestLocation() async throws -> CLLocation {
        switch manager.authorizationStatus {
        case .denied, .restricted:
            throw Failure.denied
        case .notDetermined:
            // When In Use only, and only because a button was pressed.
            manager.requestWhenInUseAuthorization()
        default:
            break
        }

        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            manager.requestLocation()
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager,
                                     didUpdateLocations locations: [CLLocation]) {
        let last = locations.last
        Task { @MainActor in
            guard let last else {
                self.finish(.failure(Failure.unavailable))
                return
            }
            self.finish(.success(last))
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager,
                                     didFailWithError error: Error) {
        Task { @MainActor in self.finish(.failure(error)) }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            // The user answered the prompt while we were waiting on it.
            guard self.continuation != nil else { return }
            switch status {
            case .authorizedWhenInUse, .authorizedAlways:
                self.manager.requestLocation()
            case .denied, .restricted:
                self.finish(.failure(Failure.denied))
            default:
                break
            }
        }
    }

    private func finish(_ result: Result<CLLocation, Error>) {
        guard let continuation else { return }
        self.continuation = nil
        continuation.resume(with: result)
    }
}
