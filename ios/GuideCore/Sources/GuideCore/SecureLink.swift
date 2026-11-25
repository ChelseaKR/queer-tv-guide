import Foundation

/// Every link the app takes from a data file is an https link.
///
/// The app never fetches these links; it hands them to the system `openURL`
/// (where to watch, the sources' pages, the license texts). A data file is
/// still only as trustworthy as the way it arrived, so no link in it is
/// taken as written:
///
/// - an `https` link is kept exactly as recorded;
/// - an `http` link is opened as `https`, same host and path, so the page
///   someone opens is never sent in the clear;
/// - anything else is not a link the app will open: another scheme (a phone
///   number, a message, another app's own scheme, a file), no host, or a
///   user name in the address.
///
/// `KeyedDecodingContainer`'s `URL` decoding below applies this to every
/// `URL` field of every type this module decodes, so a file whose own links
/// (credits, licenses, source pages, schedules) fail it is refused whole.
/// Where-to-watch links come from a third party as recorded, so one that
/// fails is left out and the rest of the file stands (`WatchLink`).
public enum SecureLink {
    /// The https form of `raw`, or `nil` when it has none.
    public static func https(_ raw: String) -> URL? {
        guard var parts = URLComponents(string: raw),
              let scheme = parts.scheme?.lowercased(),
              let host = parts.host, !host.isEmpty,
              parts.user == nil, parts.password == nil
        else { return nil }
        switch scheme {
        case "https":
            break
        case "http":
            if parts.port == 80 { parts.port = nil }
        default:
            return nil
        }
        parts.scheme = "https"
        return parts.url
    }

    static let refusal = "a link must be an https address with a host"
}

extension KeyedDecodingContainer {
    /// Chosen over the generic `decode` for a `URL`, in synthesized and
    /// hand-written `init(from:)` alike (LinkSafetyTests holds every field
    /// to it).
    func decode(_ type: URL.Type, forKey key: Key) throws -> URL {
        guard let url = SecureLink.https(try decode(String.self, forKey: key)) else {
            throw DecodingError.dataCorruptedError(forKey: key, in: self, debugDescription: SecureLink.refusal)
        }
        return url
    }

    func decodeIfPresent(_ type: URL.Type, forKey key: Key) throws -> URL? {
        guard let raw = try decodeIfPresent(String.self, forKey: key) else { return nil }
        guard let url = SecureLink.https(raw) else {
            throw DecodingError.dataCorruptedError(forKey: key, in: self, debugDescription: SecureLink.refusal)
        }
        return url
    }
}
