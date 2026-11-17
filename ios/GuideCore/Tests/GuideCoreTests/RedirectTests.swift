import XCTest
@testable import GuideCore

/// The data request stays on one host.
///
/// `SameHostRedirects` is checked two ways: its rule as a pure function, and
/// the whole refresher against a real HTTP server on this machine's loopback
/// interface, which answers with a real redirect. The server is reachable
/// under two host names (the loopback address and its name), so "another
/// host" is real: the request log says which host each request named.
///
/// The control at the bottom follows the same redirect with a plain session,
/// to prove the server redirects and the log sees a second host when nothing
/// stops it.
final class RedirectTests: XCTestCase {
    private var dir: URL!
    private var store: SnapshotStore!
    private var server: LoopbackServer!

    private static let address = "127.0.0.1"
    private static let name = "localhost"

    override func setUpWithError() throws {
        try super.setUpWithError()
        dir = try Repo.temporaryDirectory()
        store = SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL)
        server = try LoopbackServer()
    }

    override func tearDownWithError() throws {
        server.stop()
        try? FileManager.default.removeItem(at: dir)
        try super.tearDownWithError()
    }

    /// A URL on the test server, built from parts so this file holds no URL.
    private func url(host: String, path: String = "/snapshot.v1.json", port: Int? = nil, scheme: String = "http") -> URL {
        var parts = URLComponents()
        parts.scheme = scheme
        parts.host = host
        parts.port = port ?? server.port
        parts.path = path
        return parts.url!
    }

    private func newer() throws -> Data {
        try JSONEdit.edit(try Repo.fixtureData()) { $0["generated_at"] = "2026-09-14T00:00:00Z" }
    }

    // MARK: The rule

    func testOnlyTheEndpointsOwnSchemeHostAndPortAreAllowed() throws {
        let endpoint = SnapshotEndpoint.url
        let host = SnapshotEndpoint.host
        func target(_ scheme: String, _ host: String, _ rest: String = "/x.json") -> URL { URL(string: scheme + "://" + host + rest)! }
        XCTAssertTrue(SameHostRedirects.allows(target("https", host), from: endpoint))
        XCTAssertTrue(SameHostRedirects.allows(target("https", host.uppercased()), from: endpoint), "host names compare without case")
        XCTAssertTrue(SameHostRedirects.allows(target("https", host + ":443"), from: endpoint), "the scheme's own port, written out")

        XCTAssertFalse(SameHostRedirects.allows(target("https", "elsewhere.example"), from: endpoint), "another host")
        XCTAssertFalse(SameHostRedirects.allows(target("https", "www." + host), from: endpoint), "a subdomain is another host")
        XCTAssertFalse(SameHostRedirects.allows(target("https", host + ".elsewhere.example"), from: endpoint), "a longer name that starts the same")
        XCTAssertFalse(SameHostRedirects.allows(target("http", host), from: endpoint), "never down to plain HTTP")
        XCTAssertFalse(SameHostRedirects.allows(target("https", host + ":8443"), from: endpoint), "another port")
        XCTAssertFalse(SameHostRedirects.allows(target("https", "someone@" + host), from: endpoint), "a user name in the address")
        XCTAssertFalse(SameHostRedirects.allows(nil, from: endpoint))
        XCTAssertFalse(SameHostRedirects.allows(URL(string: "/relative.json"), from: endpoint), "no scheme or host of its own")
    }

    func testTheDelegateAnswersTheRedirectItIsAsked() async throws {
        let endpoint = SnapshotEndpoint.url
        let guardian = SameHostRedirects(endpoint: endpoint)
        let session = URLSession(configuration: .ephemeral)
        defer { session.invalidateAndCancel() }
        let task = session.dataTask(with: endpoint) // never resumed: no request is made
        let moved = HTTPURLResponse(url: endpoint, statusCode: 301, httpVersion: "HTTP/1.1", headerFields: nil)!
        let away = URLRequest(url: URL(string: "https" + "://elsewhere.example/snapshot.v1.json")!)
        let refused = await guardian.urlSession(session, task: task, willPerformHTTPRedirection: moved, newRequest: away)
        XCTAssertNil(refused)
        let same = URLRequest(url: endpoint.deletingLastPathComponent().appendingPathComponent("moved.json"))
        let allowed = await guardian.urlSession(session, task: task, willPerformHTTPRedirection: moved, newRequest: same)
        XCTAssertEqual(allowed?.url, same.url)
    }

    // MARK: The refresher against a real redirect

    func testARedirectToAnotherHostIsNotFollowedAndIsNoUpdateAndNoError() async throws {
        let good = try Repo.fixtureData()
        try store.replace(with: good, etag: "\"v1\"")
        let body = try newer()
        let elsewhere = url(host: Self.name)
        server.answer = { request in
            request.host.hasPrefix(Self.address)
                ? .init(status: 301, headers: ["Location": elsewhere.absoluteString], body: Data("moved".utf8))
                : .init(status: 200, headers: ["ETag": "\"other\""], body: body)
        }
        let refresher = SnapshotRefresher(store: store, endpoint: url(host: Self.address))

        let outcome = try await refresher.refresh()

        XCTAssertEqual(outcome, .unchanged, "a refused redirect is no update, and nothing is thrown")
        XCTAssertEqual(server.requests.map(\.host), ["\(Self.address):\(server.port)"], "one request, to the endpoint's host only")
        XCTAssertEqual(try Data(contentsOf: store.snapshotFileURL), good, "the stored snapshot is untouched")
        XCTAssertEqual(store.readETag(), "\"v1\"", "and so is its ETag")
    }

    func testEveryRedirectStatusIsRefusedTheSameWay() async throws {
        try store.replace(with: try Repo.fixtureData(), etag: "\"v1\"")
        let elsewhere = url(host: Self.name)
        for status in [301, 302, 303, 307, 308] {
            server.requests = []
            server.answer = { _ in .init(status: status, headers: ["Location": elsewhere.absoluteString], body: Data()) }
            let outcome = try await SnapshotRefresher(store: store, endpoint: url(host: Self.address)).refresh()
            XCTAssertEqual(outcome, .unchanged, "\(status)")
            XCTAssertEqual(server.requests.count, 1, "\(status)")
        }
    }

    func testARedirectThatStaysOnTheEndpointsHostIsFollowed() async throws {
        let body = try newer()
        let moved = url(host: Self.address, path: "/moved.json")
        server.answer = { request in
            request.path == "/moved.json"
                ? .init(status: 200, headers: ["ETag": "\"moved\""], body: body)
                : .init(status: 301, headers: ["Location": moved.absoluteString], body: Data())
        }
        let outcome = try await SnapshotRefresher(store: store, endpoint: url(host: Self.address)).refresh()
        guard case .updated = outcome else { return XCTFail("\(outcome)") }
        XCTAssertEqual(server.requests.map(\.path), ["/snapshot.v1.json", "/moved.json"])
        XCTAssertEqual(Set(server.requests.map(\.host)), ["\(Self.address):\(server.port)"])
        XCTAssertEqual(store.readETag(), "\"moved\"")
    }

    func testAPlainAnswerStillUpdatesThroughTheRealStack() async throws {
        let body = try newer()
        server.answer = { _ in .init(status: 200, headers: ["ETag": "\"new\""], body: body) }
        let outcome = try await SnapshotRefresher(store: store, endpoint: url(host: Self.address)).refresh()
        guard case .updated = outcome else { return XCTFail("\(outcome)") }
        XCTAssertEqual(server.requests.count, 1)
        XCTAssertEqual(store.readETag(), "\"new\"")
    }

    // MARK: Control

    /// Without the delegate the same redirect is followed and the second
    /// host is contacted, so the tests above can fail.
    func testControlAPlainSessionFollowsTheSameRedirectToTheOtherHost() async throws {
        let body = try newer()
        let elsewhere = url(host: Self.name)
        server.answer = { request in
            request.host.hasPrefix(Self.address)
                ? .init(status: 301, headers: ["Location": elsewhere.absoluteString], body: Data("moved".utf8))
                : .init(status: 200, headers: [:], body: body)
        }
        let session = URLSession(configuration: SnapshotRefresher.makeConfiguration())
        defer { session.invalidateAndCancel() }
        let (data, response) = try await session.data(from: url(host: Self.address))
        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 200)
        XCTAssertEqual(data, body)
        XCTAssertEqual(server.requests.map(\.host), ["\(Self.address):\(server.port)", "\(Self.name):\(server.port)"])
    }
}

/// A very small HTTP/1.1 server on the loopback interface, for one request
/// per connection. It records each request's path and Host header and
/// answers from `answer`. Plain BSD sockets from Foundation, so the tests
/// import nothing the app does not; it listens on the IPv4 and IPv6 loopback
/// addresses only, which is where the loopback's name resolves.
final class LoopbackServer: @unchecked Sendable {
    struct Request: Equatable {
        var path: String
        var host: String
    }

    struct Response {
        var status: Int
        var headers: [String: String]
        var body: Data
    }

    private var listeners: [Int32] = []
    private let lock = NSLock()
    private var _requests: [Request] = []
    private var _answer: (Request) -> Response = { _ in Response(status: 404, headers: [:], body: Data()) }

    var requests: [Request] {
        get { lock.withLock { _requests } }
        set { lock.withLock { _requests = newValue } }
    }

    var answer: (Request) -> Response {
        get { lock.withLock { _answer } }
        set { lock.withLock { _answer = newValue } }
    }

    private(set) var port: Int = 0

    init() throws {
        // IPv4 first, on any free port; then the same port on IPv6, which a
        // machine without IPv6 loopback may refuse (the name then resolves
        // to IPv4 alone).
        var v4 = sockaddr_in()
        v4.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        v4.sin_family = sa_family_t(AF_INET)
        v4.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let first = try Self.listen(family: AF_INET, address: &v4, length: MemoryLayout<sockaddr_in>.size)
        listeners.append(first)
        var bound = sockaddr_in()
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let named = withUnsafeMutablePointer(to: &bound) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(first, $0, &length) }
        }
        guard named == 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        port = Int(UInt16(bigEndian: bound.sin_port))

        var v6 = sockaddr_in6()
        v6.sin6_len = UInt8(MemoryLayout<sockaddr_in6>.size)
        v6.sin6_family = sa_family_t(AF_INET6)
        v6.sin6_port = bound.sin_port
        v6.sin6_addr = in6addr_loopback
        if let second = try? Self.listen(family: AF_INET6, address: &v6, length: MemoryLayout<sockaddr_in6>.size) {
            listeners.append(second)
        }
        for listener in listeners {
            let thread = Thread { [weak self] in self?.acceptLoop(listener) }
            thread.name = "LoopbackServer"
            thread.start()
        }
    }

    private static func listen<Address>(family: Int32, address: inout Address, length: Int) throws -> Int32 {
        let descriptor = socket(family, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        var yes: Int32 = 1
        setsockopt(descriptor, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
        let result = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { bind(descriptor, $0, socklen_t(length)) }
        }
        guard result == 0, Darwin.listen(descriptor, 16) == 0 else {
            let code = POSIXErrorCode(rawValue: errno) ?? .EIO
            close(descriptor)
            throw POSIXError(code)
        }
        return descriptor
    }

    /// Closing the listeners ends their accept loops.
    func stop() {
        for listener in listeners { close(listener) }
        listeners = []
    }

    private func acceptLoop(_ listener: Int32) {
        while true {
            let connection = accept(listener, nil, nil)
            guard connection >= 0 else { return }
            var yes: Int32 = 1
            setsockopt(connection, SOL_SOCKET, SO_NOSIGPIPE, &yes, socklen_t(MemoryLayout<Int32>.size))
            serve(connection)
            close(connection)
        }
    }

    private func serve(_ connection: Int32) {
        var received = Data()
        var buffer = [UInt8](repeating: 0, count: 16 * 1024)
        let terminator = Data("\r\n\r\n".utf8)
        while received.range(of: terminator) == nil {
            let count = recv(connection, &buffer, buffer.count, 0)
            guard count > 0 else { return }
            received.append(contentsOf: buffer[0..<count])
        }
        let head = String(decoding: received[..<received.range(of: terminator)!.lowerBound], as: UTF8.self)
        let lines = head.components(separatedBy: "\r\n")
        let target = lines.first?.split(separator: " ").dropFirst().first.map(String.init) ?? ""
        let host = lines.dropFirst()
            .first { $0.lowercased().hasPrefix("host:") }
            .map { $0.dropFirst("host:".count).trimmingCharacters(in: .whitespaces) } ?? ""
        let request = Request(path: target, host: host)
        lock.withLock { _requests.append(request) }
        let response = answer(request)
        var text = "HTTP/1.1 \(response.status) \(HTTPURLResponse.localizedString(forStatusCode: response.status))\r\n"
        for (name, value) in response.headers { text += "\(name): \(value)\r\n" }
        text += "Content-Length: \(response.body.count)\r\nConnection: close\r\n\r\n"
        var bytes = [UInt8](Data(text.utf8) + response.body)
        var sent = 0
        while sent < bytes.count {
            let count = bytes.withUnsafeMutableBytes { send(connection, $0.baseAddress! + sent, $0.count - sent, 0) }
            guard count > 0 else { return }
            sent += count
        }
    }
}
