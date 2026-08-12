import XCTest
@testable import VeloxKit

final class MITSearchTests: XCTestCase {
    private func devices() throws -> [MITDevice] {
        let base = try XCTUnwrap(Bundle.module.url(forResource: "Fixtures", withExtension: nil))
        return try Snapshot.load(from: base.appendingPathComponent("snapshot")).mitDevices
    }

    func testFindsByMatricolaCaseInsensitively() throws {
        XCTAssertEqual(MITSearch.search("tc010198", in: try devices()).count, 1)
        XCTAssertEqual(MITSearch.search("TC010198", in: try devices()).count, 1)
    }

    func testFindsByEnteSubstring() throws {
        XCTAssertEqual(MITSearch.search("Colline", in: try devices()).first?.matricola,
                       "TC010198")
    }

    func testFindsByMarcaAndModello() throws {
        XCTAssertEqual(MITSearch.search("Autovelox 106", in: try devices()).count, 1)
    }

    func testIgnoresAccentsAndPunctuation() throws {
        XCTAssertFalse(MITSearch.search("colline moreniche", in: try devices()).isEmpty)
    }

    func testEmptyQueryReturnsNothingRatherThanEverything() throws {
        XCTAssertTrue(MITSearch.search("", in: try devices()).isEmpty)
        XCTAssertTrue(MITSearch.search("   ", in: try devices()).isEmpty)
    }

    func testUnknownQueryReturnsNothing() throws {
        XCTAssertTrue(MITSearch.search("ZZZZ-not-a-device", in: try devices()).isEmpty)
    }
}
