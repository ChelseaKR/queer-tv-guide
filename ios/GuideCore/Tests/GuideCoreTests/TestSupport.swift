import Foundation
import XCTest
@testable import GuideCore

/// Locates files in the repo from this test file's compile-time path, so the
/// same tests run under `swift test` on macOS and under `xcodebuild test` in
/// the simulator (simulator processes can read the host filesystem).
enum Repo {
    /// `<repo>/ios`
    static let iosRoot: URL = {
        // .../ios/GuideCore/Tests/GuideCoreTests/TestSupport.swift
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // GuideCoreTests
            .deletingLastPathComponent() // Tests
            .deletingLastPathComponent() // GuideCore
            .deletingLastPathComponent() // ios
    }()

    static let bundledFixture: URL = iosRoot
        .appendingPathComponent("QueerTVGuide/Resources/snapshot.v1.json")

    static let privacyManifest: URL = iosRoot
        .appendingPathComponent("QueerTVGuide/PrivacyInfo.xcprivacy")

    static func fixtureData() throws -> Data {
        try Data(contentsOf: bundledFixture)
    }

    static func fixture() throws -> Snapshot {
        try SnapshotDecoder().decode(try fixtureData())
    }

    static func temporaryDirectory(_ name: String = #function) throws -> URL {
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("GuideCoreTests-\(name)-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    /// Every file under `ios/` except build products and this package's
    /// hidden SwiftPM state.
    static func sourceFiles(extensions: Set<String>) -> [URL] {
        guard let e = FileManager.default.enumerator(at: iosRoot, includingPropertiesForKeys: [.isRegularFileKey]) else { return [] }
        var out: [URL] = []
        for case let url as URL in e {
            let path = url.path
            if path.contains("/.build/") || path.contains("/DerivedData/") || path.contains("/.swiftpm/") || path.contains("/build/") {
                continue
            }
            if extensions.contains(url.pathExtension) {
                out.append(url)
            }
        }
        return out.sorted { $0.path < $1.path }
    }
}

/// Mutates a JSON fixture in memory so a test can produce a near-real
/// document with one field changed.
enum JSONEdit {
    static func edit(_ data: Data, _ mutate: (inout [String: Any]) -> Void) throws -> Data {
        var object = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        mutate(&object)
        return try JSONSerialization.data(withJSONObject: object)
    }

    static func editShow(_ data: Data, index: Int, _ mutate: (inout [String: Any]) -> Void) throws -> Data {
        try edit(data) { root in
            var shows = root["shows"] as! [[String: Any]]
            mutate(&shows[index])
            root["shows"] = shows
        }
    }

    static func editCharacter(_ data: Data, index: Int, _ mutate: (inout [String: Any]) -> Void) throws -> Data {
        try edit(data) { root in
            var chars = root["characters"] as! [[String: Any]]
            mutate(&chars[index])
            root["characters"] = chars
        }
    }
}

/// A URLProtocol that answers from a script. Registered per-session via
/// `protocolClasses`, so nothing here touches the global registry.
final class StubURLProtocol: URLProtocol {
    struct Response {
        var status: Int
        var headers: [String: String]
        var body: Data
    }

    nonisolated(unsafe) static var handler: ((URLRequest) -> Response)?
    nonisolated(unsafe) static var recorded: [URLRequest] = []

    static func reset() {
        handler = nil
        recorded = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.recorded.append(request)
        guard let handler = Self.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
            return
        }
        let r = handler(request)
        let http = HTTPURLResponse(url: request.url!, statusCode: r.status, httpVersion: "HTTP/1.1", headerFields: r.headers)!
        client?.urlProtocol(self, didReceive: http, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: r.body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
