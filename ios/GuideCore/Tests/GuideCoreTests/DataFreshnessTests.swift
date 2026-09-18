import XCTest
@testable import GuideCore

/// DG-04 in the app: the snapshot's age against the 48-hour staleness SLA
/// the data cards state, and what the app says about it.
final class DataFreshnessTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_790_000_000)
    private let hour: TimeInterval = 60 * 60

    private func assess(age: TimeInterval) -> DataFreshness {
        DataFreshness.assess(generatedAt: now.addingTimeInterval(-age), now: now)
    }

    // MARK: Thresholds

    func testAFreshSnapshotIsCurrentWithItsAge() {
        XCTAssertEqual(assess(age: 5 * hour), .current(age: 5 * hour))
        XCTAssertTrue(assess(age: 5 * hour).isCurrent)
    }

    func testExactlyTheSLAIsStillCurrentAndOneSecondMoreIsStale() {
        XCTAssertEqual(DataFreshness.staleAfter, 48 * hour)
        XCTAssertEqual(assess(age: 48 * hour), .current(age: 48 * hour))
        XCTAssertEqual(assess(age: 48 * hour + 1), .stale(age: 48 * hour + 1))
        XCTAssertFalse(assess(age: 48 * hour + 1).isCurrent)
    }

    func testAWeeksOldBundledCopyIsStale() {
        XCTAssertEqual(assess(age: 21 * 24 * hour), .stale(age: 21 * 24 * hour))
    }

    /// A device clock a little fast or slow is normal: a snapshot dated up
    /// to an hour ahead reads as brand new, not as unknown.
    func testASnapshotSlightlyAheadOfTheClockIsCurrentAtAgeZero() {
        XCTAssertEqual(assess(age: -30 * 60), .current(age: 0))
        XCTAssertEqual(assess(age: -hour), .current(age: 0))
    }

    /// Past the tolerance the age cannot be known, and unknown is never
    /// current.
    func testASnapshotDatedFurtherAheadHasAnUnknownAgeNeverCurrent() {
        let freshness = assess(age: -hour - 1)
        XCTAssertEqual(freshness, .unknown)
        XCTAssertFalse(freshness.isCurrent)
    }

    // MARK: The SLA is the one the data cards publish

    /// The number in the data card's "Staleness SLA" row, in hours.
    static func slaHours(inCard text: String) -> Int? {
        guard let row = text.split(separator: "\n").first(where: { $0.hasPrefix("| Staleness SLA |") }) else { return nil }
        let cell = row.dropFirst("| Staleness SLA |".count)
        let digits = cell.drop { !$0.isNumber }.prefix { $0.isNumber }
        return Int(digits)
    }

    func testTheAppUsesTheSLAThatBothDataCardsState() throws {
        for card in ["lezwatch.md", "tvmaze.md"] {
            let url = Repo.iosRoot.deletingLastPathComponent().appendingPathComponent("docs/data/\(card)")
            let text = try String(contentsOf: url, encoding: .utf8)
            XCTAssertEqual(Self.slaHours(inCard: text).map { TimeInterval($0) * hour }, DataFreshness.staleAfter, "\(card)'s Staleness SLA and DataFreshness.staleAfter disagree")
        }
    }

    /// Negative control for the check above: a card whose SLA was edited
    /// must read differently, or the agreement test proves nothing.
    func testTheDataCardReaderSeesAnEditedSLA() throws {
        let url = Repo.iosRoot.deletingLastPathComponent().appendingPathComponent("docs/data/lezwatch.md")
        let real = try String(contentsOf: url, encoding: .utf8)
        let edited = real.replacingOccurrences(of: "| Staleness SLA | 48 hours", with: "| Staleness SLA | 72 hours")
        XCTAssertNotEqual(edited, real, "the sabotage did not land: the card's SLA row has a different shape")
        XCTAssertEqual(Self.slaHours(inCard: real), 48)
        XCTAssertEqual(Self.slaHours(inCard: edited), 72)
        XCTAssertNil(Self.slaHours(inCard: "no table here"))
    }

    // MARK: What the app says

    func testCurrentDataCarriesNoWarningAndSaysHowOldItIs() {
        let generated = now.addingTimeInterval(-5 * hour)
        let freshness = DataFreshness.assess(generatedAt: generated, now: now)
        XCTAssertNil(Presentation.freshnessWarning(generatedAt: generated, freshness: freshness))
        let line = Presentation.dataAsOf(generated, freshness: freshness)
        XCTAssertTrue(line.hasPrefix("Data as of "), line)
        XCTAssertTrue(line.hasSuffix("(5 hours ago)"), line)
    }

    func testStaleDataSaysSoPlainly() throws {
        let generated = now.addingTimeInterval(-5 * 24 * hour)
        let freshness = DataFreshness.assess(generatedAt: generated, now: now)
        let warning = try XCTUnwrap(Presentation.freshnessWarning(generatedAt: generated, freshness: freshness))
        XCTAssertEqual(warning.title, "This data is out of date")
        XCTAssertTrue(warning.detail.hasPrefix("It was last updated 5 days ago, on "), warning.detail)
        XCTAssertTrue(warning.spoken.hasPrefix("Warning. This data is out of date. "), warning.spoken)
        XCTAssertTrue(Presentation.dataAsOf(generated, freshness: freshness).hasSuffix("(5 days ago)"))
    }

    /// An unknown age is stated as unknown: a warning, never a blank, never
    /// "no", and the data-status line says so too.
    func testUnknownAgeIsStatedNeverPresentedAsCurrent() throws {
        let generated = now.addingTimeInterval(3 * 24 * hour)
        let freshness = DataFreshness.assess(generatedAt: generated, now: now)
        let warning = try XCTUnwrap(Presentation.freshnessWarning(generatedAt: generated, freshness: freshness))
        XCTAssertEqual(warning.title, "This data's age is unknown")
        XCTAssertTrue(warning.detail.contains("later than this device's clock"), warning.detail)
        XCTAssertNil(warning.spoken.range(of: #"^\s*No\b"#, options: [.regularExpression, .caseInsensitive]), warning.spoken)
        let line = Presentation.dataAsOf(generated, freshness: freshness)
        XCTAssertTrue(line.hasPrefix("Data as of "), line)
        XCTAssertTrue(line.contains("age unknown"), line)
        XCTAssertFalse(line.contains(" ago)"), line)
    }

    func testAgeWordingAtItsBoundaries() {
        XCTAssertEqual(Presentation.age(0), "less than an hour ago")
        XCTAssertEqual(Presentation.age(-10), "less than an hour ago")
        XCTAssertEqual(Presentation.age(hour - 1), "less than an hour ago")
        XCTAssertEqual(Presentation.age(hour), "1 hour ago")
        XCTAssertEqual(Presentation.age(2 * hour), "2 hours ago")
        XCTAssertEqual(Presentation.age(48 * hour - 1), "47 hours ago")
        XCTAssertEqual(Presentation.age(48 * hour + 1), "2 days ago")
        XCTAssertEqual(Presentation.age(72 * hour - 1), "2 days ago", "rounded down, never overstated")
        XCTAssertEqual(Presentation.age(30 * 24 * hour), "30 days ago")
    }

    // MARK: On the snapshot the app ships

    /// The real bundled snapshot, judged at its own date plus an offset:
    /// current just after publication, stale once past the SLA.
    func testTheBundledSnapshotGoesStaleAfterTheSLA() throws {
        let snapshot = try SnapshotDecoder().decode(try Data(contentsOf: Repo.bundledSnapshot))
        let published = snapshot.generatedAt
        XCTAssertTrue(DataFreshness.assess(generatedAt: published, now: published.addingTimeInterval(hour)).isCurrent)
        XCTAssertEqual(
            DataFreshness.assess(generatedAt: published, now: published.addingTimeInterval(49 * hour)),
            .stale(age: 49 * hour)
        )
    }
}
