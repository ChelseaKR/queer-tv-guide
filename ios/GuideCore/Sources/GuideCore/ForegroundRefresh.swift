import Foundation

/// When coming back to the app should look for new data.
///
/// An iPhone keeps an app suspended for days, so the launch-time refresh may
/// be days behind by the time someone returns. Returning to the foreground
/// makes the same single conditional GET as a launch or a pull to refresh (no
/// new host, no identifier, no telemetry), but only when the data on hand is
/// old enough to be worth it, and never more than once in `minimumInterval`.
/// It runs in the background: the screen never waits on it, and a failed
/// attempt leaves the current snapshot exactly as it was.
///
/// The two numbers live here, once. `Presentation.refreshTriggers` builds the
/// sentence the out-of-date banner and the About screen show from them, and a
/// test holds the privacy policy and the support page to the same words.
public struct ForegroundRefreshGate: Equatable, Sendable {
    /// Returning to the app looks for new data once the snapshot on hand is
    /// more than this old: three days. (The out-of-date banner appears at 48
    /// hours, `DataFreshness.staleAfter`; this is deliberately later, so a
    /// short absence costs no request at all.)
    public static let staleAfter: TimeInterval = 3 * 24 * 60 * 60

    /// At most one look on return per this long, however often the app comes
    /// to the foreground, and whether or not the last look succeeded. A phone
    /// that is offline is not asked again on every unlock.
    public static let minimumInterval: TimeInterval = 6 * 60 * 60

    /// When the app last looked for new data, from any trigger (launch, pull
    /// to refresh, or a return to the foreground). Held in memory only: it is
    /// never written to disk, so nothing about when someone opens the app is
    /// kept.
    public private(set) var lastAttempt: Date?

    public init(lastAttempt: Date? = nil) {
        self.lastAttempt = lastAttempt
    }

    /// Notes that a look for new data is starting at `now`, whatever
    /// triggered it.
    public mutating func recordAttempt(at now: Date) {
        lastAttempt = now
    }

    /// Whether returning to the app at `now`, holding a snapshot generated at
    /// `generatedAt`, should look for new data. When it says yes it also
    /// records the attempt, so the answer to a second question within
    /// `minimumInterval` is no.
    ///
    /// - A snapshot no older than `staleAfter` is current enough: no.
    /// - A snapshot dated later than the device's clock allows (its age
    ///   cannot be known, `DataFreshness.unknown`) is treated like a stale
    ///   one, as the banner does: a new file may settle it.
    /// - A look already made less than `minimumInterval` ago: no. If the
    ///   device's clock has moved back past the last look, the interval
    ///   cannot be measured, so the look is allowed.
    public mutating func shouldRefresh(
        generatedAt: Date,
        now: Date,
        staleAfter: TimeInterval = ForegroundRefreshGate.staleAfter,
        minimumInterval: TimeInterval = ForegroundRefreshGate.minimumInterval
    ) -> Bool {
        let age = now.timeIntervalSince(generatedAt)
        let ageUnknown = age < -DataFreshness.clockTolerance
        guard ageUnknown || age > staleAfter else { return false }
        if let last = lastAttempt {
            let since = now.timeIntervalSince(last)
            if since >= 0, since < minimumInterval { return false }
        }
        lastAttempt = now
        return true
    }
}
