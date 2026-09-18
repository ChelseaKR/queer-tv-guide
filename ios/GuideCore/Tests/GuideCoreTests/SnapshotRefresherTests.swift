import XCTest
@testable import GuideCore

final class SnapshotRefresherTests: XCTestCase {
    private var dir: URL!
    private var store: SnapshotStore!

    override func setUpWithError() throws {
        try super.setUpWithError()
        dir = try Repo.temporaryDirectory()
        store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        StubURLProtocol.reset()
    }

    override func tearDownWithError() throws {
        StubURLProtocol.reset()
        try? FileManager.default.removeItem(at: dir)
        try super.tearDownWithError()
    }

    private func refresher() -> SnapshotRefresher {
        SnapshotRefresher(store: store, protocolClasses: [StubURLProtocol.self])
    }

    // MARK: Posture

    func testConfigurationHasNoCookiesNoCacheNoCredentials() {
        let c = SnapshotRefresher.makeConfiguration()
        XCTAssertNil(c.httpCookieStorage)
        XCTAssertFalse(c.httpShouldSetCookies)
        XCTAssertEqual(c.httpCookieAcceptPolicy, .never)
        XCTAssertNil(c.urlCache)
        XCTAssertNil(c.urlCredentialStorage)
        XCTAssertEqual(c.requestCachePolicy, .reloadIgnoringLocalAndRemoteCacheData)
        XCTAssertEqual(c.httpAdditionalHeaders?.count, 1, "only Accept; no identifiers")
        XCTAssertEqual(c.httpAdditionalHeaders?["Accept"] as? String, "application/json")
    }

    func testRequestIsPlainGETToTheEndpoint() {
        let r = refresher().makeRequest(etag: nil)
        XCTAssertEqual(r.httpMethod, "GET")
        XCTAssertEqual(r.url, SnapshotEndpoint.url)
        XCTAssertEqual(r.url?.scheme, "https")
        XCTAssertNil(r.httpBody)
        XCTAssertFalse(r.httpShouldHandleCookies)
        XCTAssertEqual(r.allHTTPHeaderFields ?? [:], [:], "no headers at all without an ETag")
    }

    func testRequestCarriesIfNoneMatchWhenETagKnown() {
        let r = refresher().makeRequest(etag: "\"abc\"")
        XCTAssertEqual(r.allHTTPHeaderFields, ["If-None-Match": "\"abc\""])
    }

    // MARK: Outcomes

    func test200ReplacesSnapshotAndStoresETag() async throws {
        let newer = try JSONEdit.edit(try Repo.fixtureData()) { $0["generated_at"] = "2026-09-14T00:00:00Z" }
        StubURLProtocol.handler = { _ in .init(status: 200, headers: ["ETag": "\"new\""], body: newer) }
        let outcome = try await refresher().refresh()
        guard case .updated(let s) = outcome else { return XCTFail("\(outcome)") }
        XCTAssertEqual(s.generatedAt, ISO8601SecondFormatter.date(from: "2026-09-14T00:00:00Z"))
        XCTAssertEqual(store.readETag(), "\"new\"")
        XCTAssertEqual(try store.load().origin, .downloaded)
    }

    func test304LeavesEverythingAlone() async throws {
        try store.replace(with: try Repo.fixtureData(), etag: "\"v1\"")
        StubURLProtocol.handler = { _ in .init(status: 304, headers: [:], body: Data()) }
        let outcome = try await refresher().refresh()
        XCTAssertEqual(outcome, .unchanged)
        XCTAssertEqual(store.readETag(), "\"v1\"")
        XCTAssertEqual(StubURLProtocol.recorded.first?.value(forHTTPHeaderField: "If-None-Match"), "\"v1\"", "the stored ETag was sent")
    }

    func testServerErrorKeepsLastGood() async throws {
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        StubURLProtocol.handler = { _ in .init(status: 503, headers: [:], body: Data("down".utf8)) }
        do {
            _ = try await refresher().refresh()
            XCTFail("expected an error")
        } catch let error as SnapshotRefresher.RefreshError {
            XCTAssertEqual(error, .httpStatus(503))
        }
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
        XCTAssertEqual(store.readETag(), "\"v1\"")
    }

    func testGarbage200KeepsLastGood() async throws {
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        StubURLProtocol.handler = { _ in .init(status: 200, headers: ["ETag": "\"bad\""], body: Data("<html>captive portal</html>".utf8)) }
        do {
            _ = try await refresher().refresh()
            XCTFail("expected an error")
        } catch let error as SnapshotRefresher.RefreshError {
            guard case .rejected = error else { return XCTFail("\(error)") }
        }
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
        XCTAssertEqual(store.readETag(), "\"v1\"", "a captive-portal body must not advance the ETag")
    }

    func testTransportFailureKeepsLastGood() async throws {
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        StubURLProtocol.handler = nil // stub fails with notConnectedToInternet
        do {
            _ = try await refresher().refresh()
            XCTFail("expected an error")
        } catch let error as SnapshotRefresher.RefreshError {
            guard case .transport = error else { return XCTFail("\(error)") }
        }
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good)
    }

    func testExactlyOneRequestPerRefreshAndNoCookieHeader() async throws {
        StubURLProtocol.handler = { _ in .init(status: 304, headers: [:], body: Data()) }
        _ = try await refresher().refresh()
        XCTAssertEqual(StubURLProtocol.recorded.count, 1)
        let sent = StubURLProtocol.recorded[0]
        XCTAssertNil(sent.value(forHTTPHeaderField: "Cookie"))
        XCTAssertNil(sent.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(sent.url?.host, SnapshotEndpoint.host)
    }
}
