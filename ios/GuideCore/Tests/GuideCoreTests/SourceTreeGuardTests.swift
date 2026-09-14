import XCTest
@testable import GuideCore

/// Static gates over `ios/`. These fail the build if the product's premise
/// stops being literally true: one host, one URLSession, no third-party
/// code, a privacy manifest that matches the APIs actually used, and the
/// placeholder product name in exactly one place.
final class SourceTreeGuardTests: XCTestCase {
    /// Text files that could carry a URL or an import. `.json` is data the
    /// app only ever hands to `openURL`; it is scanned by `testJSONDataFilesAreNotFetched`
    /// instead of the host gate.
    private static let codeExtensions: Set<String> = ["swift", "plist", "xcprivacy", "xcconfig", "pbxproj", "xcscheme", "xcstrings", "entitlements", "xctestplan"]

    private static let hostPattern = try! NSRegularExpression(pattern: #"https?://([A-Za-z0-9.-]+)"#)

    /// The plist DOCTYPE line carries a DTD identifier that is never fetched.
    private static let dtdToken = "http://www.apple.com/DTDs/PropertyList-1.0.dtd"

    private func read(_ url: URL) throws -> String {
        try String(contentsOf: url, encoding: .utf8)
    }

    private func swiftFiles() -> [URL] {
        Repo.sourceFiles(extensions: ["swift"])
    }

    private func codeFiles() -> [URL] {
        var files = Repo.sourceFiles(extensions: Self.codeExtensions)
        // Makefile has no extension.
        let makefile = Repo.iosRoot.appendingPathComponent("Makefile")
        if FileManager.default.fileExists(atPath: makefile.path) { files.append(makefile) }
        return files
    }

    // MARK: 1. One host

    func testOnlyTheSnapshotHostAppearsInSource() throws {
        var offenders: [String] = []
        for file in codeFiles() {
            let text = try read(file).replacingOccurrences(of: Self.dtdToken, with: "")
            let range = NSRange(text.startIndex..., in: text)
            for m in Self.hostPattern.matches(in: text, range: range) {
                let host = String(text[Range(m.range(at: 1), in: text)!]).lowercased()
                if host != SnapshotEndpoint.host.lowercased() {
                    offenders.append("\(file.lastPathComponent): \(host)")
                }
            }
        }
        XCTAssertEqual(offenders, [], "hosts other than \(SnapshotEndpoint.host) found in ios/: \(offenders)")
    }

    func testSnapshotEndpointIsHTTPS() {
        XCTAssertEqual(SnapshotEndpoint.url.scheme, "https")
        XCTAssertFalse(SnapshotEndpoint.host.isEmpty)
    }

    // MARK: 2. One URLSession, no other network code

    func testExactlyOneURLSessionConstructionSite() throws {
        var sites: [String] = []
        for file in swiftFiles() where !file.path.contains("/Tests/") && !file.path.contains("Tests/") {
            let text = try read(file)
            for line in text.split(separator: "\n") where line.contains("URLSession(") || line.contains("URLSession.shared") {
                sites.append("\(file.lastPathComponent): \(line.trimmingCharacters(in: .whitespaces))")
            }
        }
        XCTAssertEqual(sites.count, 1, "expected exactly one URLSession construction, found: \(sites)")
        XCTAssertTrue(sites.first?.hasPrefix("SnapshotRefresher.swift") ?? false, "\(sites)")
    }

    func testNoOtherNetworkOrWebPrimitives() throws {
        let banned = ["NWConnection", "NWBrowser", "CFStreamCreatePair", "NSURLConnection", "WKWebView", "SFSafariViewController", "getaddrinfo", "CFSocket", "NSStream", "URLSessionWebSocketTask", "MultipeerConnectivity", "CKContainer", "NSUbiquitousKeyValueStore", "SKPaymentQueue", "StoreKit"]
        var offenders: [String] = []
        for file in swiftFiles() where !file.path.contains("Tests/") {
            let text = try read(file)
            for token in banned where text.contains(token) {
                offenders.append("\(file.lastPathComponent): \(token)")
            }
        }
        XCTAssertEqual(offenders, [])
    }

    // MARK: 3. No third-party code

    func testImportsAreSystemOrOurs() throws {
        let allowed: Set<String> = ["Foundation", "SwiftUI", "XCTest", "Observation", "GuideCore", "QueerTVGuide", "PackageDescription", "UIKit"]
        let importLine = try NSRegularExpression(pattern: #"^\s*(?:@testable\s+)?import\s+([A-Za-z_][A-Za-z0-9_]*)"#, options: [.anchorsMatchLines])
        var offenders: [String] = []
        for file in swiftFiles() {
            let text = try read(file)
            for m in importLine.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
                let module = String(text[Range(m.range(at: 1), in: text)!])
                if !allowed.contains(module) { offenders.append("\(file.lastPathComponent): import \(module)") }
            }
        }
        XCTAssertEqual(offenders, [], "unexpected imports: \(offenders)")
    }

    func testNoRemotePackagesOrPods() throws {
        for file in Repo.sourceFiles(extensions: ["pbxproj"]) {
            let text = try read(file)
            XCTAssertFalse(text.contains("XCRemoteSwiftPackageReference"), "\(file.lastPathComponent) references a remote package")
            XCTAssertFalse(text.contains("Pods"), "\(file.lastPathComponent) references CocoaPods")
        }
        XCTAssertFalse(FileManager.default.fileExists(atPath: Repo.iosRoot.appendingPathComponent("Podfile").path))
        let packageText = try read(Repo.iosRoot.appendingPathComponent("GuideCore/Package.swift"))
        XCTAssertFalse(packageText.contains("dependencies: [\n        .package"), "GuideCore must not depend on other packages")
        XCTAssertFalse(packageText.contains(".package(url"), "GuideCore must not depend on other packages")
    }

    // MARK: 4. Privacy manifest matches reality

    private func manifest() throws -> [String: Any] {
        let data = try Data(contentsOf: Repo.privacyManifest)
        return try XCTUnwrap(PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any])
    }

    func testPrivacyManifestDeclaresNothingCollectedAndNoTracking() throws {
        let m = try manifest()
        XCTAssertEqual(m["NSPrivacyTracking"] as? Bool, false)
        XCTAssertEqual((m["NSPrivacyTrackingDomains"] as? [Any])?.count, 0)
        XCTAssertEqual((m["NSPrivacyCollectedDataTypes"] as? [Any])?.count, 0)
    }

    func testPrivacyManifestDeclaresExactlyTheRequiredReasonAPIsUsed() throws {
        let m = try manifest()
        let declared = try XCTUnwrap(m["NSPrivacyAccessedAPITypes"] as? [[String: Any]])
        let declaredCategories = Set(declared.compactMap { $0["NSPrivacyAccessedAPIType"] as? String })

        // What the app source actually touches (tests excluded).
        var text = ""
        for file in swiftFiles() where !file.path.contains("Tests/") { text += try read(file) }

        let usesUserDefaults = text.contains("UserDefaults")
        let usesFileTimestamp = ["creationDate", "modificationDate", "fileModificationDate", "contentModificationDateKey", "creationDateKey", "getattrlist", "fstat(", "stat(", "lstat(", "fstatat("].contains { text.contains($0) }
        let usesBootTime = ["systemUptime", "mach_absolute_time", "mach_continuous_time"].contains { text.contains($0) }
        let usesDiskSpace = ["volumeAvailableCapacity", "volumeTotalCapacity", "statfs(", "fstatfs(", "systemFreeSize", "systemSize"].contains { text.contains($0) }
        let usesKeyboards = text.contains("activeInputModes")

        func expect(_ category: String, _ used: Bool, reasons: [String]) {
            if used {
                XCTAssertTrue(declaredCategories.contains(category), "\(category) is used but not declared in PrivacyInfo.xcprivacy")
                let entry = declared.first { $0["NSPrivacyAccessedAPIType"] as? String == category }
                let got = Set((entry?["NSPrivacyAccessedAPITypeReasons"] as? [String]) ?? [])
                XCTAssertEqual(got, Set(reasons), "\(category) reasons")
            } else {
                XCTAssertFalse(declaredCategories.contains(category), "\(category) is declared but not used; remove it so the manifest stays exact")
            }
        }

        expect("NSPrivacyAccessedAPICategoryUserDefaults", usesUserDefaults, reasons: ["CA92.1"])
        expect("NSPrivacyAccessedAPICategoryFileTimestamp", usesFileTimestamp, reasons: ["C617.1"])
        expect("NSPrivacyAccessedAPICategorySystemBootTime", usesBootTime, reasons: ["35F9.1"])
        expect("NSPrivacyAccessedAPICategoryDiskSpace", usesDiskSpace, reasons: ["E174.1"])
        expect("NSPrivacyAccessedAPICategoryActiveKeyboards", usesKeyboards, reasons: ["3EC4.1"])
        XCTAssertEqual(declaredCategories.count, declared.count, "duplicate category entries")
    }

    // MARK: 5. Placeholder name lives in one place

    // This guard file necessarily names the placeholder and the rejected
    // name in its own source (to describe what it's checking for), so it
    // excludes itself from both scans below — every other file in ios/ is
    // still checked without exception.
    private static let thisFileName = "SourceTreeGuardTests.swift"

    func testPlaceholderProductNameAppearsExactlyOnce() throws {
        let placeholder = "Queer TV Guide"
        var hits: [String] = []
        var files = codeFiles()
        files += Repo.sourceFiles(extensions: ["json", "md", "strings"])
        for file in files where file.lastPathComponent != Self.thisFileName {
            let text = try read(file)
            let n = text.components(separatedBy: placeholder).count - 1
            if n > 0 { hits.append("\(file.lastPathComponent) ×\(n)") }
        }
        XCTAssertEqual(hits, ["AppIdentity.swift ×1"], "the placeholder name must live only in AppIdentity.swift; found: \(hits)")
    }

    func testTheWordSignalIsNotUsedAsAName() throws {
        // DECISIONS 0004: never "Signal". (A fixture episode title is data, not a name; the check is on code files.)
        for file in codeFiles() where file.lastPathComponent != Self.thisFileName {
            let text = try read(file)
            XCTAssertFalse(text.contains("\"Signal\""), "\(file.lastPathComponent) uses the rejected name")
        }
    }

    // MARK: 6. Data files are never fetched

    func testJSONDataFilesAreNotFetched() throws {
        // The only JSON the app parses from the network is the snapshot body
        // returned by the one GET; every other .json in ios/ is a bundled
        // resource read with Data(contentsOf: <file URL>).
        var text = ""
        for file in swiftFiles() where !file.path.contains("Tests/") { text += try read(file) }
        XCTAssertFalse(text.contains("Data(contentsOf: URL(string:"), "a URL(string:) fed to Data(contentsOf:) is a hidden network fetch")
    }
}
