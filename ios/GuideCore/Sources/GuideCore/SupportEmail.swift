import Foundation

/// The "Email support" row in About (DECISIONS 0039): a `mailto:` link to
/// the address the support page lists (DECISIONS 0015), handed to the
/// system `openURL`, so iOS opens the person's own mail app with a new
/// message. The app sends nothing itself: no host, no request, no form,
/// and nothing about the device or what someone follows goes in the draft.
/// The subject names the app and its version so a reply can say which
/// build is meant; the person can edit or delete it before sending.
public enum SupportEmail {
    /// The address on `docs/site/support.html` and the Play listing.
    public static let address = "chelsea@chelseakr.com"

    /// "<app name> <version>", or the app name alone when the version is
    /// missing or blank: an unknown version is left out, never written as
    /// a placeholder.
    public static func subject(appName: String, version: String?) -> String {
        let version = version?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return version.isEmpty ? appName : "\(appName) \(version)"
    }

    /// Unreserved characters (RFC 3986): everything else in the subject is
    /// percent-encoded, "&", "=", "?" and "+" included, so nothing in it can
    /// end the subject or add another header.
    private static let unreserved = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~")

    /// `mailto:<address>?subject=<subject>`, with the subject percent-encoded.
    public static func url(appName: String, version: String?) -> URL {
        let encoded = subject(appName: appName, version: version)
            .addingPercentEncoding(withAllowedCharacters: unreserved) ?? ""
        return URL(string: "mailto:\(address)?subject=\(encoded)")!
    }
}
