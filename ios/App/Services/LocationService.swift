import Foundation
import CoreLocation
import VeloxKit

/// Wraps CLLocationManager and republishes positions as `VeloxKit.Fix`.
///
/// Authorisation is When In Use only — trip mode is explicit and foreground-armed.
/// Background updates are enabled only while a trip is armed and cleared on stop.
@MainActor
@Observable
final class LocationService: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private(set) var latestFix: Fix?
    private(set) var authorizationStatus: CLAuthorizationStatus = .notDetermined
    private var armed = false

    override init() {
        super.init()
        manager.delegate = self
        manager.activityType = .automotiveNavigation
        manager.desiredAccuracy = kCLLocationAccuracyBestForNavigation
        authorizationStatus = manager.authorizationStatus
    }

    func start() {
        armed = true
        if manager.authorizationStatus == .notDetermined {
            // When In Use only. Never requestAlwaysAuthorization.
            manager.requestWhenInUseAuthorization()
        }
        enableBackgroundUpdatesIfAuthorized()
        manager.startUpdatingLocation()
    }

    func stop() {
        armed = false
        manager.stopUpdatingLocation()
        manager.allowsBackgroundLocationUpdates = false
        manager.pausesLocationUpdatesAutomatically = true
        latestFix = nil
    }

    private func enableBackgroundUpdatesIfAuthorized() {
        guard armed else { return }
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            manager.allowsBackgroundLocationUpdates = true
            manager.pausesLocationUpdatesAutomatically = false
        default:
            break
        }
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            self.authorizationStatus = status
            self.enableBackgroundUpdatesIfAuthorized()
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager,
                                     didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        // course < 0 means unknown; it must become nil, not 0, or alerts
        // would silently be gated to northbound travel only.
        let fix = Fix(
            coordinate: Coordinate(lat: location.coordinate.latitude,
                                   lon: location.coordinate.longitude),
            courseDegrees: location.course >= 0 ? location.course : nil,
            speedMetresPerSecond: max(0, location.speed),
            timestamp: location.timestamp.timeIntervalSince1970
        )
        Task { @MainActor in
            self.latestFix = fix
        }
    }
}
