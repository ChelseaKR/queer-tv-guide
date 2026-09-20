import Foundation

/// The ONE network location this app ever contacts. Everything else the app
/// opens (where-to-watch, attribution links) goes through the system
/// `openURL`, i.e. Safari, not this process.
///
/// The URL is published in `schema/README.md` (owned by the pipeline lane):
/// GitHub Pages serving the static file out of this private repo. The app
/// makes one conditional GET with `If-None-Match` against the stored ETag
/// (`SnapshotRefresher`); if the server returns 304 Not Modified, the cached
/// copy is kept. This achieves the same "skip the megabytes when nothing
/// changed" property in one request instead of two.
///
/// `SourceTreeGuardTests` asserts that no other host appears anywhere in
/// `ios/`.
public enum SnapshotEndpoint {
    public static let url = URL(string: "https://chelseakr.github.io/queer-tv-guide/snapshot.v1.json")!
    public static var host: String { url.host! }
}

/// The privacy policy, published by the same nightly workflow onto the same
/// GitHub Pages site as the snapshot (so no new host). App Review 5.1.1(i)
/// wants it linked inside the app as well as in App Store Connect. It opens
/// in Safari via `openURL`; the app itself never fetches it.
public enum PrivacyPolicy {
    public static let url = URL(string: "https://chelseakr.github.io/queer-tv-guide/privacy.html")!
}

/// The support page (DECISIONS 0010): the App Store Support URL, published by
/// the same nightly workflow onto the same Pages site. Opened in Safari via
/// `openURL`; the app never fetches it.
public enum SupportPage {
    public static let url = URL(string: "https://chelseakr.github.io/queer-tv-guide/support.html")!
}
