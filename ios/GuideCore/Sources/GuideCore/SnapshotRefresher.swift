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
public final class SnapshotRefresher: @unchecked Sendable {
    public enum Outcome: Equatable, Sendable {
        /// Server answered 304: the stored snapshot is already current.
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
        self.session = URLSession(configuration: Self.makeConfiguration(protocolClasses: protocolClasses))
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
    public func refresh() async throws -> Outcome {
        let request = makeRequest(etag: store.readETag())
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw RefreshError.transport(error.localizedDescription)
        }
        guard let http = response as? HTTPURLResponse else { throw RefreshError.notHTTP }
        switch http.statusCode {
        case 304:
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
