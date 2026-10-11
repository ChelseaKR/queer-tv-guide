import Foundation

/// Why a look for new data failed, sorted the way a person can act on it.
/// The raw system error ("The Internet connection appears to be offline.",
/// "The data file server answered HTTP 503.") says what broke, not what it
/// means for the screen. In every case the data already on the phone stays
/// exactly as it was (`SnapshotRefresher`), and the words say so.
public enum RefreshProblem: Equatable, Sendable {
    /// The system reports no connection: airplane mode, no signal, Wi-Fi
    /// without internet that iOS already knows about.
    case offline
    /// Online, but no usable answer from the data server: a timeout, a
    /// DNS or TLS failure, a captive portal that refused the connection, or
    /// an HTTP error status.
    case unreachable
    /// The server answered with a file that failed the app's checks (it
    /// would not decode, or broke a rule such as attribution or unique ids),
    /// so it was not used.
    case unusable

    /// `URLError` codes that mean "no connection at all", as opposed to
    /// "connected, but the server did not answer".
    static let offlineCodes: Set<URLError.Code> = [
        .notConnectedToInternet,
        .networkConnectionLost,
        .dataNotAllowed,
        .internationalRoamingOff,
        .callIsActive,
    ]

    static func isOffline(_ error: Error) -> Bool {
        if let urlError = error as? URLError { return offlineCodes.contains(urlError.code) }
        let ns = error as NSError
        return ns.domain == NSURLErrorDomain && offlineCodes.contains(URLError.Code(rawValue: ns.code))
    }

    /// Sorts any error `SnapshotRefresher.refresh()` throws. Anything it
    /// does not recognize counts as `unreachable`: the data was not
    /// replaced, and the server is the likeliest reason.
    public init(_ error: Error) {
        switch error as? SnapshotRefresher.RefreshError {
        case .transport(_, offline: true)?: self = .offline
        case .rejected?: self = .unusable
        case .transport?, .httpStatus?, .notHTTP?, nil: self = .unreachable
        }
    }

    /// One sentence for the data footer: what happened, then that the data
    /// on screen is kept. The date line beside it says how old that is.
    public var message: String {
        switch self {
        case .offline:
            return "Couldn't check for new data: this device is offline. The data below stays as it is."
        case .unreachable:
            return "Couldn't reach the data server. The data below stays as it is."
        case .unusable:
            return "A new data file arrived but failed the app's checks, so it wasn't used. The data below stays as it is."
        }
    }
}
