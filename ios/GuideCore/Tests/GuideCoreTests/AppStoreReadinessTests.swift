import Foundation
import XCTest
@testable import GuideCore

/// Submission requirements that live in config and docs rather than code,
/// checked where CI can see them (`swift test`).
final class AppStoreReadinessTests: XCTestCase {
    private var repoRoot: URL { Repo.iosRoot.deletingLastPathComponent() }

    private func settings(_ xcconfig: String) throws -> [String: String] {
        let text = try String(contentsOf: Repo.iosRoot.appendingPathComponent("Config/\(xcconfig)"), encoding: .utf8)
        var out: [String: String] = [:]
        for line in text.split(separator: "\n") {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard !trimmed.hasPrefix("//"), let eq = trimmed.firstIndex(of: "=") else { continue }
            let key = trimmed[..<eq].trimmingCharacters(in: .whitespaces)
            out[key] = trimmed[trimmed.index(after: eq)...].trimmingCharacters(in: .whitespaces)
        }
        return out
    }

    /// The target supports iPad (TARGETED_DEVICE_FAMILY 1,2); App Store
    /// upload validation rejects an iPad-capable build that does not declare
    /// all four orientations for multitasking.
    func testIPadDeclaresAllFourOrientations() throws {
        let shared = try settings("Shared.xcconfig")
        let product = try settings("Product.xcconfig")
        guard shared["TARGETED_DEVICE_FAMILY"]?.contains("2") == true else {
            throw XCTSkip("iPad is not a target; the orientation rule does not apply")
        }
        let iPad = Set((product["INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad"] ?? "").split(separator: " ").map(String.init))
        XCTAssertEqual(iPad, [
            "UIInterfaceOrientationPortrait",
            "UIInterfaceOrientationPortraitUpsideDown",
            "UIInterfaceOrientationLandscapeLeft",
            "UIInterfaceOrientationLandscapeRight",
        ])
        XCTAssertNotNil(product["INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone"])
    }

    func testExportComplianceAndCategoryAreDeclared() throws {
        let product = try settings("Product.xcconfig")
        XCTAssertEqual(product["INFOPLIST_KEY_ITSAppUsesNonExemptEncryption"], "NO")
        XCTAssertEqual(product["INFOPLIST_KEY_LSApplicationCategoryType"], "public.app-category.entertainment")
    }

    /// Same host as the snapshot, so the one-host guard still holds and no
    /// new party learns anything.
    func testPrivacyPolicyLivesOnTheSnapshotHost() {
        XCTAssertEqual(PrivacyPolicy.url.scheme, "https")
        XCTAssertEqual(PrivacyPolicy.url.host, SnapshotEndpoint.host)
        XCTAssertEqual(PrivacyPolicy.url.lastPathComponent, "privacy.html")
    }

    /// The page the workflow publishes: present, published by the workflow,
    /// no scripts or third-party requests of its own, and no product name
    /// baked in while the name is undecided (DECISIONS 0004).
    func testPrivacyPolicyPageIsPublishedStaticAndNameless() throws {
        let page = try String(contentsOf: repoRoot.appendingPathComponent("docs/site/privacy.html"), encoding: .utf8)
        XCTAssertTrue(page.contains(SnapshotEndpoint.url.absoluteString), "the policy must name the one URL the app requests")
        XCTAssertTrue(page.contains("IP address"), "the policy must say what the one request reveals")
        for banned in ["<script", "<link", "<img", "<iframe", "src=", "@import"] {
            XCTAssertFalse(page.lowercased().contains(banned), "privacy.html must make no requests of its own: found \(banned)")
        }
        XCTAssertFalse(page.contains(["Queer", "TV", "Guide"].joined(separator: " ")), "the product name is undecided; the policy says \"the app\"")
        // Spelled in pieces so this file does not trip the source-tree guard
        // against the rejected name (DECISIONS 0004).
        XCTAssertFalse(page.contains("Sig" + "nal"), "never the rejected name")

        let workflow = try String(contentsOf: repoRoot.appendingPathComponent(".github/workflows/snapshot.yml"), encoding: .utf8)
        XCTAssertTrue(workflow.contains("cp ../docs/site/privacy.html site/privacy.html"), "the nightly workflow must publish the policy")
    }
}
