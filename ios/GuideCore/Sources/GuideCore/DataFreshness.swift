import Foundation

/// How old the snapshot on screen is, judged against the staleness SLA the
/// data cards state (`docs/data/lezwatch.md`, `docs/data/tvmaze.md`: 48
/// hours). DATA-GOVERNANCE-STANDARD DG-04: data older than its SLA is said to
/// be out of date, never shown as current.
///
/// Three states, and only `.current` is current. A snapshot dated later than
/// this device's clock cannot be aged at all (the clock is wrong, or the file
/// is), so it is `.unknown`, and the UI treats unknown exactly like stale:
/// an answer nobody can give is never shown as "fine".
public enum DataFreshness: Equatable, Sendable {
    /// Within the SLA. `age` is in seconds, never negative.
    case current(age: TimeInterval)
    /// Older than the SLA. `age` is in seconds.
    case stale(age: TimeInterval)
    /// Dated more than `clockTolerance` after `now`, so its age is unknown.
    case unknown

    /// The data cards' staleness SLA. The nightly run publishes every 24
    /// hours (`snapshot.yml`, 09:17 UTC), and a healthy snapshot measured
    /// at most about 24 h 10 min old just before the next one replaced it
    /// (2026-09-15 to 09-18), so 48 hours is reached only after a nightly
    /// run has been missed and the next one is late or missed too.
    public static let staleAfter: TimeInterval = 48 * 60 * 60

    /// How far in the future a snapshot's date may be before its age is
    /// treated as unknown. A device clock a few minutes fast is normal; one
    /// an hour behind the server's is not something to guess past.
    public static let clockTolerance: TimeInterval = 60 * 60

    /// Judges `generatedAt` (the snapshot's `generated_at`) at `now`.
    /// Exactly `staleAfter` old is still current; one second more is stale.
    public static func assess(generatedAt: Date, now: Date) -> DataFreshness {
        let age = now.timeIntervalSince(generatedAt)
        if age < -clockTolerance { return .unknown }
        let clamped = max(0, age)
        return clamped > staleAfter ? .stale(age: clamped) : .current(age: clamped)
    }

    public var isCurrent: Bool {
        if case .current = self { return true }
        return false
    }
}
