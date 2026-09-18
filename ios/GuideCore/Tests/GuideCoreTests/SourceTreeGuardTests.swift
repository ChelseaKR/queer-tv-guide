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
    // "yml" covers `project.yml`: XcodeGen's source of truth for
    // QueerTVGuide.xcodeproj (see the Makefile — `xcodegen generate`
    // regenerates the committed .pbxproj from it). A host or a remote
    // package added there would otherwise reach the real build without
    // ever being scanned, since it isn't Swift, a plist, or the pbxproj
    // itself.
    private static let codeExtensions: Set<String> = ["swift", "plist", "xcprivacy", "xcconfig", "pbxproj", "xcscheme", "xcstrings", "entitlements", "xctestplan", "yml"]

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
        // UserNotifications: Apple's local notification scheduler, for the
        // optional episode reminders (off behind FeatureFlags). Local only:
        // no push, no server.
        let allowed: Set<String> = ["Foundation", "SwiftUI", "XCTest", "Observation", "GuideCore", "QueerTVGuide", "PackageDescription", "UIKit", "UserNotifications"]
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

        // project.yml is XcodeGen's source of truth for QueerTVGuide.xcodeproj
        // (Makefile: "xcodegen generate regenerates ... from project.yml").
        // A remote package declared there (XcodeGen's `url:` key) would only
        // show up in the .pbxproj scan above after a regenerate; catch it at
        // the source instead. The one legitimate package (GuideCore) uses
        // `path:`, never `url:`.
        let projectYMLText = try read(Repo.iosRoot.appendingPathComponent("project.yml"))
        XCTAssertFalse(projectYMLText.contains("url:"), "project.yml declares a package by url: (remote); only path: (local, like GuideCore) is allowed")
    }

    /// Regression guard for the check above: proves the `url:` substring
    /// test actually matches the shapes XcodeGen's own docs show for a
    /// remote package (quoted, unquoted, with any version-constraint key),
    /// and does not false-positive on the local `path:` syntax GuideCore
    /// legitimately uses.
    func testProjectYMLRemotePackageDetectionCatchesRealisticXcodeGenSyntax() {
        // Built with a split scheme, not a literal "https://…", so this
        // file's own fixture strings don't trip `testOnlyTheSnapshotHostAppearsInSource`
        // (which scans every .swift file, this one included).
        let scheme = "https"
        let remoteExamples = [
            "packages:\n  SomeSDK:\n    url: \(scheme)://example.com/sdk\n    from: 1.0.0\n",
            "packages:\n  SomeSDK:\n    url: \"\(scheme)://example.com/sdk\"\n    exactVersion: 2.1.0\n",
            "packages:\n  SomeSDK:\n    url: git@example.com:sdk.git\n    branch: main\n",
        ]
        for example in remoteExamples {
            XCTAssertTrue(example.contains("url:"), "remote package example should be detected: \(example)")
        }
        let localExample = "packages:\n  GuideCore:\n    path: GuideCore\n"
        XCTAssertFalse(localExample.contains("url:"), "a local path: package must not false-positive")
    }

    /// Regression guard for `testOnlyTheSnapshotHostAppearsInSource`: proves
    /// `project.yml` is actually in the scanned file set, not just that
    /// "yml" is in the extension list (a typo in the enumerator's filter
    /// could still skip it silently).
    func testProjectYMLIsScannedForHosts() {
        XCTAssertTrue(Self.codeExtensions.contains("yml"), "project.yml must be scanned for stray hosts")
        let matches = codeFiles().filter { $0.lastPathComponent == "project.yml" }
        XCTAssertEqual(matches.count, 1, "project.yml must be included in the scanned file set")
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

    /// Reminders are local notifications only. No remote-notification
    /// registration, no push entitlement, no background mode: the app never
    /// gets a device token to send anywhere.
    func testRemindersAreLocalOnly() throws {
        var text = ""
        for file in swiftFiles() where !file.path.contains("Tests/") { text += try read(file) }
        for token in ["registerForRemoteNotifications", "UNNotificationServiceExtension", "didRegisterForRemoteNotificationsWithDeviceToken", "PKPushRegistry"] {
            XCTAssertFalse(text.contains(token), "\(token) would reach a push server")
        }
        for file in Repo.sourceFiles(extensions: ["entitlements", "plist", "xcconfig", "yml"]) {
            let body = try read(file)
            XCTAssertFalse(body.contains("aps-environment"), "\(file.lastPathComponent) asks for push")
            XCTAssertFalse(body.contains("remote-notification"), "\(file.lastPathComponent) asks for a remote-notification background mode")
        }
    }

    // MARK: 5. The product name lives in two places that agree

    // This guard file necessarily names the product, the old placeholder
    // and the rejected name in its own source (to describe what it's
    // checking for), so it excludes itself from the scans below — every
    // other file in ios/ is still checked without exception.
    private static let thisFileName = "SourceTreeGuardTests.swift"

    /// DECISIONS 0006. The Swift constant and the home-screen display name.
    static let productName = "Queer Frame"

    private func scannedFiles() -> [URL] {
        var files = codeFiles()
        files += Repo.sourceFiles(extensions: ["json", "md", "strings"])
        return files.filter { $0.lastPathComponent != Self.thisFileName }
    }

    func testProductNameIsSpelledOutInExactlyTheTwoPlacesThatNameTheApp() throws {
        var hits: [String] = []
        for file in scannedFiles() {
            let n = try read(file).components(separatedBy: Self.productName).count - 1
            if n > 0 { hits.append("\(file.lastPathComponent) ×\(n)") }
        }
        XCTAssertEqual(Set(hits), ["AppIdentity.swift ×1", "Product.xcconfig ×1"], "the product name must be spelled out only in AppIdentity.swift and as CFBundleDisplayName in Product.xcconfig; found: \(hits)")
    }

    func testDisplayNameAndAppIdentityAgree() throws {
        let identity = try read(Repo.iosRoot.appendingPathComponent("QueerTVGuide/App/AppIdentity.swift"))
        XCTAssertTrue(identity.contains("static let displayName = \"\(Self.productName)\""), "AppIdentity.displayName is not the product name")
        let product = try read(Repo.iosRoot.appendingPathComponent("Config/Product.xcconfig"))
        XCTAssertTrue(product.split(separator: "\n").contains { $0.trimmingCharacters(in: .whitespaces) == "INFOPLIST_KEY_CFBundleDisplayName = \(Self.productName)" }, "CFBundleDisplayName is not the product name")
    }

    func testTheOldPlaceholderNameIsGone() throws {
        let placeholder = "Queer TV Guide"
        var hits: [String] = []
        for file in scannedFiles() {
            if try read(file).contains(placeholder) { hits.append(file.lastPathComponent) }
        }
        XCTAssertEqual(hits, [], "the working placeholder name is still user-visible in: \(hits)")
    }

    func testTheWordSignalIsNotUsedAsAName() throws {
        // DECISIONS 0004/0006: never "Signal". (A fixture episode title is data, not a name; the check is on code files.)
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
