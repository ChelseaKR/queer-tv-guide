import Foundation

/// A place inside the app that something outside the current screen can
/// open: a widget row, a reminder, or (later) a Spotlight result.
///
/// The URL form, `queerframe://show/<id>`, never leaves the device. It is
/// not a web address, carries nothing but a snapshot id, and opening it
/// sends no request: the app looks the id up in the snapshot it already
/// has. An id the snapshot does not have opens the show screen's own
/// "Show not found" state rather than failing silently.
public enum AppLink: Equatable, Hashable, Sendable {
    case show(Show.ID)
    case character(Character.ID)

    /// The app's registered URL scheme (`ios/QueerTVGuide/Info.plist`).
    public static let scheme = "queerframe"

    /// The `userInfo` key a reminder carries its show id under.
    public static let reminderShowIDKey = "showID"

    public var url: URL {
        var components = URLComponents()
        components.scheme = Self.scheme
        switch self {
        case .show(let id):
            components.host = "show"
            components.path = "/" + id
        case .character(let id):
            components.host = "character"
            components.path = "/" + id
        }
        // Ids are LezWatch.TV's ("lwtv:show:26"): letters, digits and
        // colons, which URLComponents keeps as they are in a path.
        return components.url!
    }

    /// Reads a link this app made. Anything else (another scheme, an
    /// unknown kind, an empty or nested id) is nil, so a malformed link
    /// does nothing rather than open the wrong screen.
    public init?(url: URL) {
        guard url.scheme?.lowercased() == Self.scheme,
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let kind = components.host?.lowercased()
        else { return nil }
        let path = components.path
        guard path.hasPrefix("/") else { return nil }
        let id = String(path.dropFirst())
        guard !id.isEmpty, !id.contains("/") else { return nil }
        switch kind {
        case "show": self = .show(id)
        case "character": self = .character(id)
        default: return nil
        }
    }
}
