import Foundation

/// What the Share button hands to the system share sheet: a show's
/// LezWatch.TV page and nothing else.
public enum Sharing {
    /// `url` with any query, fragment and credentials removed, so a shared
    /// link carries no tracking parameters and nothing about who shared it.
    /// The snapshot's page links carry none today (checked on the real
    /// snapshot in `SharingTests`); this keeps it so if one ever does.
    public static func cleanURL(_ url: URL) -> URL {
        guard var components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return url }
        components.query = nil
        components.fragment = nil
        components.user = nil
        components.password = nil
        return components.url ?? url
    }
}
