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

    /// DECISIONS 0009: iPhone only. No iPad family, no iPad-only keys left
    /// behind, and the iPhone orientations declared.
    func testIPhoneOnly() throws {
        let shared = try settings("Shared.xcconfig")
        let product = try settings("Product.xcconfig")
        XCTAssertEqual(shared["TARGETED_DEVICE_FAMILY"], "1", "iPhone only (DECISIONS 0009)")
        XCTAssertNil(product["INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad"], "an iPad key on an iPhone-only target")
        XCTAssertNotNil(product["INFOPLIST_KEY_UISupportedInterfaceOrientations_iPhone"])
    }

    func testExportComplianceAndCategoryAreDeclared() throws {
        let product = try settings("Product.xcconfig")
        XCTAssertEqual(product["INFOPLIST_KEY_ITSAppUsesNonExemptEncryption"], "NO")
        XCTAssertEqual(product["INFOPLIST_KEY_LSApplicationCategoryType"], "public.app-category.entertainment")
    }

    /// Same host as the snapshot, so the one-host guard still holds and no
    /// new party learns anything.
    func testPrivacyAndSupportPagesLiveOnTheSnapshotHost() {
        for (url, file) in [(PrivacyPolicy.url, "privacy.html"), (SupportPage.url, "support.html")] {
            XCTAssertEqual(url.scheme, "https")
            XCTAssertEqual(url.host, SnapshotEndpoint.host)
            XCTAssertEqual(url.lastPathComponent, file)
        }
    }

    /// The product name as the app spells it (AppIdentity.swift), read from
    /// source so this file never spells it itself.
    private func productName() throws -> String {
        let identity = try String(contentsOf: Repo.iosRoot.appendingPathComponent("QueerTVGuide/App/AppIdentity.swift"), encoding: .utf8)
        let marker = "static let displayName = \""
        let start = try XCTUnwrap(identity.range(of: marker)).upperBound
        let end = try XCTUnwrap(identity[start...].firstIndex(of: "\""))
        return String(identity[start..<end])
    }

    /// The pages the workflow publishes: present, published, linked, static
    /// (no requests of their own), and named with the product's name.
    func testPrivacyAndSupportPagesArePublishedStaticAndNamed() throws {
        let name = try productName()
        let workflow = try String(contentsOf: repoRoot.appendingPathComponent(".github/workflows/snapshot.yml"), encoding: .utf8)
        for file in ["privacy.html", "support.html"] {
            let page = try String(contentsOf: repoRoot.appendingPathComponent("docs/site/\(file)"), encoding: .utf8)
            for banned in ["<script", "<link", "<img", "<iframe", "src=", "@import"] {
                XCTAssertFalse(page.lowercased().contains(banned), "\(file) must make no requests of its own: found \(banned)")
            }
            XCTAssertTrue(page.contains("<title>\(name) "), "\(file) must carry the product name in its title")
            XCTAssertFalse(page.contains(["Queer", "TV", "Guide"].joined(separator: " ")), "\(file) still uses the old placeholder name")
            // Spelled in pieces so this file does not trip the source-tree
            // guard against the rejected name (DECISIONS 0004).
            XCTAssertFalse(page.contains("Sig" + "nal"), "never the rejected name")
            XCTAssertTrue(workflow.contains("cp ../docs/site/\(file) site/\(file)"), "the nightly workflow must publish \(file)")
        }
        let privacy = try String(contentsOf: repoRoot.appendingPathComponent("docs/site/privacy.html"), encoding: .utf8)
        XCTAssertTrue(privacy.contains(SnapshotEndpoint.url.absoluteString), "the policy must name the one URL the app requests")
        // DECISIONS 0007: who serves the file, what it sees, what the app collects.
        XCTAssertTrue(privacy.contains("served by GitHub"), "the policy must say GitHub serves the data file")
        XCTAssertTrue(privacy.contains("IP address"), "the policy must say the host sees request IPs")
        XCTAssertTrue(privacy.contains("\(name) collects nothing"), "the policy must say the app collects nothing")
        XCTAssertTrue(privacy.contains("href=\"support.html\""), "the policy must link the support page")
        let support = try String(contentsOf: repoRoot.appendingPathComponent("docs/site/support.html"), encoding: .utf8)
        XCTAssertTrue(support.contains("href=\"privacy.html\""), "the support page must link the policy")
    }

    // MARK: The App Store listing (docs/app-store-listing.json)

    private func listing() throws -> [String: Any] {
        let data = try Data(contentsOf: repoRoot.appendingPathComponent("docs/app-store-listing.json"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    /// Apple's App Store Connect limits, in characters.
    func testListingFieldsFitAppStoreConnectLimits() throws {
        let l = try listing()
        let limits: [(String, Int)] = [("name", 30), ("subtitle", 30), ("promotional_text", 170), ("keywords", 100), ("description", 4000)]
        for (field, limit) in limits {
            let value = try XCTUnwrap(l[field] as? String, "\(field) missing")
            XCTAssertFalse(value.isEmpty, "\(field) is empty")
            XCTAssertLessThanOrEqual(value.count, limit, "\(field) is \(value.count) characters; the limit is \(limit)")
        }
        let keywords = try XCTUnwrap(l["keywords"] as? String)
        XCTAssertFalse(keywords.contains(", "), "a space after a keyword comma wastes one of the 100 characters")
    }

    /// Words already in the name or subtitle earn nothing as keywords.
    func testKeywordsDoNotRepeatNameOrSubtitleWords() throws {
        let l = try listing()
        func words(_ s: String) -> Set<String> {
            Set(s.lowercased().split(whereSeparator: { !$0.isLetter }).map(String.init))
        }
        let taken = words((l["name"] as? String ?? "") + " " + (l["subtitle"] as? String ?? ""))
        let repeated = words(l["keywords"] as? String ?? "").intersection(taken)
        XCTAssertEqual(repeated, [], "keywords repeat name/subtitle words")
    }

    /// Copy rule (docs/APP-STORE.md): no market-uniqueness claims.
    func testCustomerCopyMakesNoOnlyOrFirstClaims() throws {
        let l = try listing()
        for field in ["subtitle", "promotional_text", "description"] {
            let words = Set((l[field] as? String ?? "").lowercased().split(whereSeparator: { !$0.isLetter }).map(String.init))
            XCTAssertTrue(words.isDisjoint(with: ["only", "first", "best"]), "\(field) makes an only/first/best claim")
        }
    }

    /// The listing matches the build: name, device family, URLs, price.
    func testListingMatchesTheBuild() throws {
        let l = try listing()
        XCTAssertEqual(l["name"] as? String, try productName(), "App Store name must be the app's display name")
        XCTAssertEqual(l["devices"] as? [String], ["iPhone"], "DECISIONS 0009")
        XCTAssertEqual(try settings("Shared.xcconfig")["TARGETED_DEVICE_FAMILY"], "1")
        XCTAssertEqual(l["support_url"] as? String, SupportPage.url.absoluteString)
        XCTAssertEqual(l["privacy_policy_url"] as? String, PrivacyPolicy.url.absoluteString)
        XCTAssertEqual(l["price_usd"] as? String, "4.99", "DECISIONS 0011")
    }
}
