import XCTest
@testable import VeloxKit

final class CopyTests: XCTestCase {
    /// Every string the app can show a user, gathered in one place.
    private var allUserFacingStrings: [String] {
        [
            Copy.fixedCameraAlert(metres: 800),
            Copy.scheduledRoadAlert(road: "SS9", province: "LO"),
            Copy.emptyState(publishedAt: "10/08/2026"),
            Copy.coverageDisclaimer,
            Copy.stalenessBanner(days: 9),
            Copy.regionUnavailable(region: "Sicilia"),
            Copy.noFixedInstallations,
            Copy.mitRegisterExplainer(deviceCount: 4110),
            Copy.mitSearchPrompt,
            Copy.mitNoMatch,
            Copy.stretchEntryAlert(road: "A4"),
            Copy.appPurpose,
            Copy.routeIntro,
            Copy.dataCoverage(from: "10/08", to: "16/08", publishedAt: "13/08/2026"),
            Copy.dataAsOf(publishedAt: "13/08/2026"),
            Copy.refreshFailed(publishedAt: "13/08/2026"),
        ]
    }

    func testNoStringMakesAnAllClearClaim() {
        for string in allUserFacingStrings {
            let lowered = string.lowercased()
            for forbidden in Copy.forbiddenPhrases {
                XCTAssertFalse(lowered.contains(forbidden),
                               "\"\(string)\" contains the forbidden phrase \"\(forbidden)\"")
            }
        }
    }

    func testEmptyStateNamesTheAuthorityAndCarriesTheDate() {
        let text = Copy.emptyState(publishedAt: "10/08/2026")
        XCTAssertTrue(text.lowercased().contains("polizia stradale"))
        XCTAssertTrue(text.contains("10/08/2026"))
    }

    func testCoverageDisclaimerStatesTheLimit() {
        XCTAssertTrue(Copy.coverageDisclaimer.lowercased().contains("polizia stradale"))
        XCTAssertTrue(Copy.coverageDisclaimer.lowercased().contains("comun"),
                      "the disclaimer must explain that municipal devices are not included")
    }

    func testFixedAlertCarriesTheDistanceAndTheLimit() {
        let text = Copy.fixedCameraAlert(metres: 800)
        XCTAssertTrue(text.contains("800"))
        XCTAssertTrue(text.lowercased().contains("limite"))
    }
}

extension CopyTests {
    /// A freshness message without a date tells the user nothing about whether
    /// to trust the screen.
    func testFreshnessMessagesAlwaysCarryTheDate() {
        XCTAssertTrue(Copy.dataAsOf(publishedAt: "13/08/2026").contains("13/08/2026"))
        XCTAssertTrue(Copy.refreshFailed(publishedAt: "13/08/2026").contains("13/08/2026"))
    }
}
