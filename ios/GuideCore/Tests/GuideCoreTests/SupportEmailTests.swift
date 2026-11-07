import Foundation
import XCTest
@testable import GuideCore

/// The About screen's "Email support" row (DECISIONS 0039): a mailto link to
/// the support page's address, with the app and version in the subject.
/// The product name is passed in (it may be spelled out only in
/// AppIdentity.swift, `SourceTreeGuardTests`), so these tests use a stand-in.
final class SupportEmailTests: XCTestCase {
    private let appName = "Example App"

    func testURLIsAMailtoToTheSupportAddressWithTheVersionInTheSubject() throws {
        let url = SupportEmail.url(appName: appName, version: "1.0.1")
        XCTAssertEqual(url.scheme, "mailto")
        XCTAssertNil(url.host, "a mailto link names no host the app could reach")
        let parts = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false))
        XCTAssertEqual(parts.path, SupportEmail.address)
        XCTAssertEqual(parts.queryItems, [URLQueryItem(name: "subject", value: "Example App 1.0.1")])
        XCTAssertEqual(url.absoluteString, "mailto:\(SupportEmail.address)?subject=Example%20App%201.0.1")
    }

    /// Absence is never a value: no version means no version in the subject,
    /// not "—", "unknown" or "nil".
    func testAMissingOrBlankVersionIsLeftOut() {
        XCTAssertEqual(SupportEmail.subject(appName: appName, version: nil), appName)
        XCTAssertEqual(SupportEmail.subject(appName: appName, version: ""), appName)
        XCTAssertEqual(SupportEmail.subject(appName: appName, version: "  \n"), appName)
        XCTAssertEqual(SupportEmail.subject(appName: appName, version: " 2.3 "), "Example App 2.3")
        XCTAssertFalse(SupportEmail.url(appName: appName, version: nil).absoluteString.contains("nil"))
    }

    /// Reserved characters in the subject cannot add a second header (a
    /// "&body=" or "&cc=" smuggled in through the version string).
    func testTheSubjectCannotAddOtherHeaders() throws {
        let url = SupportEmail.url(appName: appName, version: "1.0&cc=someone@example.com")
        let items = try XCTUnwrap(URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems)
        XCTAssertEqual(items.map(\.name), ["subject"])
        XCTAssertEqual(items.first?.value, "Example App 1.0&cc=someone@example.com")
    }

    /// The same address the published support page and the Play listing give.
    func testAddressMatchesTheSupportPageAndThePlayListing() throws {
        let root = Repo.iosRoot.deletingLastPathComponent()
        let support = try String(contentsOf: root.appendingPathComponent("docs/site/support.html"), encoding: .utf8)
        XCTAssertTrue(support.contains("mailto:\(SupportEmail.address)"), "support.html does not list \(SupportEmail.address)")
        let play = try String(contentsOf: root.appendingPathComponent("docs/play-store/play-listing.json"), encoding: .utf8)
        XCTAssertTrue(play.contains("\"contact_email\": \"\(SupportEmail.address)\""), "the Play listing's contact email is not \(SupportEmail.address)")
    }
}
