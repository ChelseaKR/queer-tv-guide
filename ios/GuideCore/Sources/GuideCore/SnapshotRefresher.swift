import Foundation

/// The app's entire network surface: one HTTPS GET of a static file.
///
/// - No cookies (storage nil, never accepted, never sent).
/// - No URLCache: the app keeps its own file and its own ETag, and sends
///   `If-None-Match` itself. Nothing else persists from a session.
/// - No identifiers: no custom headers beyond `Accept` and `If-None-Match`.
///   (URLSession's default `User-Agent` names the bundle and CFNetwork
///   version; that is the platform's, not ours, and identifies nobody.)
/// - Ephemeral configuration: no credential store, no on-disk session state.
/// - One host: a redirect is followed only when it stays on the endpoint's
///   own scheme, host and port (`SameHostRedirects`). A redirect to anywhere
///   else is not followed, so no request is ever made to another host.
public final class SnapshotRefresher: @unchecked Sendable {
    public enum Outcome: Equatable, Sendable {
        /// Nothing new was taken and nothing failed: the stored snapshot
        /// stays. Either the server answered 304 (it is already current), or
        /// it answered with a redirect that was not followed.
        case unchanged
        /// A new snapshot decoded and was swapped in.
        case updated(Snapshot)
    }

    public enum RefreshError: Error, Equatable, LocalizedError {
        case httpStatus(Int)
        case notHTTP
        case transport(String)
        case rejected(String)

        public var errorDescription: String? {
            switch self {
            case .httpStatus(let code): return "The data file server answered HTTP \(code)."
            case .notHTTP: return "The data file server did not answer over HTTP."
            case .transport(let s): return s
            case .rejected(let s): return s
            }
        }
    }

    private let session: URLSession
    private let store: SnapshotStore
    private let endpoint: URL

    public init(store: SnapshotStore, endpoint: URL = SnapshotEndpoint.url, protocolClasses: [AnyClass]? = nil) {
        self.store = store
        self.endpoint = endpoint
        self.session = URLSession(configuration: Self.makeConfiguration(protocolClasses: protocolClasses), delegate: SameHostRedirects(endpoint: endpoint), delegateQueue: nil)
    }

    /// The single `URLSessionConfiguration` in the app. Exposed so tests can
    /// assert its posture without going through the network.
    public static func makeConfiguration(protocolClasses: [AnyClass]? = nil) -> URLSessionConfiguration {
        let c = URLSessionConfiguration.ephemeral
        c.httpCookieStorage = nil
        c.httpShouldSetCookies = false
        c.httpCookieAcceptPolicy = .never
        c.urlCache = nil
        c.urlCredentialStorage = nil
        c.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        c.waitsForConnectivity = false
        c.timeoutIntervalForRequest = 20
        c.timeoutIntervalForResource = 60
        c.httpAdditionalHeaders = ["Accept": "application/json"]
        if let protocolClasses { c.protocolClasses = protocolClasses }
        return c
    }

    /// Builds the exact request that will be sent. Pure; tests inspect it.
    public func makeRequest(etag: String?) -> URLRequest {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "GET"
        request.httpShouldHandleCookies = false
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        if let etag, !etag.isEmpty {
            request.setValue(etag, forHTTPHeaderField: "If-None-Match")
        }
        return request
    }

    /// Performs the GET. On success the store is updated; on any failure the
    /// store is untouched and the error is thrown for the UI to state.
    ///
    /// A request cancelled before it answered (SwiftUI cancels a pull to
    /// refresh's task when its screen goes away) throws `CancellationError`,
    /// not a `RefreshError`: nothing failed, and URLSession's own wording
    /// for it is the bare word "cancelled".
    ///
    /// A redirect that `SameHostRedirects` did not follow arrives here as
    /// the redirect's own 3xx answer. It is `.unchanged`: no update, and no
    /// error for the UI to state.
    public func refresh() async throws -> Outcome {
        let request = makeRequest(etag: store.readETag())
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch let error as URLError where error.code == .cancelled {
            throw CancellationError()
        } catch let error as CancellationError {
            throw error
        } catch {
            throw RefreshError.transport(error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else { throw RefreshError.notHTTP }
        switch http.statusCode {
        case 304:
            return .unchanged
        case 300..<400:
            return .unchanged
        case 200:
            let etag = http.value(forHTTPHeaderField: "ETag")
            do {
                let snapshot = try store.replace(with: data, etag: etag)
                return .updated(snapshot)
            } catch let error as SnapshotDecodingError {
                throw RefreshError.rejected(error.localizedDescription)
            } catch {
                throw RefreshError.rejected(error.localizedDescription)
            }
        default:
            throw RefreshError.httpStatus(http.statusCode)
        }
    }
}

/// Keeps the data request on one host. URLSession follows any redirect
/// unless its delegate says otherwise; this delegate lets one through only
/// when it stays on the endpoint's own scheme, host and port. For any other
/// redirect the request stops where it is, no request is made to the other
/// host, and the redirect's own answer is what `refresh()` sees.
public final class SameHostRedirects: NSObject, URLSessionTaskDelegate, Sendable {
    private let endpoint: URL

    public init(endpoint: URL) {
        self.endpoint = endpoint
    }

    /// Whether a redirect to `target` stays on `endpoint`'s scheme, host and
    /// port. Host names compare without case; a missing port is the
    /// scheme's own.
    public static func allows(_ target: URL?, from endpoint: URL) -> Bool {
        guard let target,
              let scheme = target.scheme?.lowercased(), scheme == endpoint.scheme?.lowercased(),
              let host = target.host?.lowercased(), !host.isEmpty, host == endpoint.host?.lowercased(),
              target.user == nil, target.password == nil
        else { return false }
        let standard = scheme == "https" ? 443 : 80
        return (target.port ?? standard) == (endpoint.port ?? standard)
    }

    public func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest) async -> URLRequest? {
        Self.allows(request.url, from: endpoint) ? request : nil
    }
}
