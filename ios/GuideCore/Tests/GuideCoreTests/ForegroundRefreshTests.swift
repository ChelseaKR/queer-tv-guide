import XCTest
@testable import GuideCore

/// Returning to the app looks for new data when the data on hand is old
/// enough, at most once in a stated interval (`ForegroundRefreshGate`), and
/// everything that says so (the banner, About, the privacy policy, the
/// support page) is built from, or held to, the same two numbers.
final class ForegroundRefreshTests: XCTestCase {
    private let hour: TimeInterval = 3600
    private let day: TimeInterval = 24 * 3600
    private let generatedAt = ISO8601SecondFormatter.date(from: "2026-09-10T09:00:00Z")!

    private func now(agedBy age: TimeInterval) -> Date { generatedAt.addingTimeInterval(age) }

    // MARK: The two numbers

    /// The threshold and the interval are named constants, in one place.
    func testTheThresholdAndTheIntervalAreTheNamedConstants() {
        XCTAssertEqual(ForegroundRefreshGate.staleAfter, 3 * day, "several days: three")
        XCTAssertEqual(ForegroundRefreshGate.minimumInterval, 6 * hour)
        XCTAssertGreaterThan(ForegroundRefreshGate.staleAfter, DataFreshness.staleAfter, "later than the banner's 48 hours, on purpose")
    }

    // MARK: The decision

    func testAStaleSnapshotTriggersOneRefreshAndReturningAgainDoesNot() {
        var gate = ForegroundRefreshGate()
        let returning = now(agedBy: 4 * day)
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: returning))
        XCTAssertEqual(gate.lastAttempt, returning, "the attempt is recorded")
        // Back and forth to the app within the interval: no more looks.
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: returning.addingTimeInterval(60)))
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: returning.addingTimeInterval(6 * hour - 1)))
        // After the interval, still stale (the refresh failed or found nothing newer): once more.
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: returning.addingTimeInterval(6 * hour)))
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: returning.addingTimeInterval(6 * hour + 60)))
    }

    func testACurrentSnapshotDoesNotTriggerARefreshOnReturn() {
        var gate = ForegroundRefreshGate()
        for age in [0, hour, 24 * hour, 47 * hour, ForegroundRefreshGate.staleAfter] {
            XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: age)), "age \(age / hour) hours")
        }
        XCTAssertNil(gate.lastAttempt, "a refusal records nothing")
    }

    func testJustPastTheThresholdTriggers() {
        var gate = ForegroundRefreshGate()
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: ForegroundRefreshGate.staleAfter)), "exactly the threshold is not past it")
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: ForegroundRefreshGate.staleAfter + 1)))
    }

    func testBetweenTheBannerAndTheThresholdNothingIsRequested() {
        // The banner says "out of date" from 48 hours; the return refresh
        // starts at 3 days. The banner's wording says exactly that, so this
        // gap is stated, not hidden (see the wording tests below).
        var gate = ForegroundRefreshGate()
        let age = DataFreshness.staleAfter + hour
        XCTAssertFalse(DataFreshness.assess(generatedAt: generatedAt, now: now(agedBy: age)).isCurrent)
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: age)))
    }

    func testAnUnknownAgeIsTreatedLikeAStaleSnapshot() {
        var gate = ForegroundRefreshGate()
        // Dated two hours after the device's clock: its age cannot be known.
        let clock = now(agedBy: -2 * hour)
        XCTAssertEqual(DataFreshness.assess(generatedAt: generatedAt, now: clock), .unknown)
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: clock))
        // A few minutes ahead is a normal clock difference, not unknown.
        var other = ForegroundRefreshGate()
        XCTAssertFalse(other.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: -10 * 60)))
    }

    func testALookFromAnotherTriggerCountsTowardTheInterval() {
        // Launch and pull to refresh record their attempts too, so returning
        // right after either does not look again.
        var gate = ForegroundRefreshGate()
        let launch = now(agedBy: 5 * day)
        gate.recordAttempt(at: launch)
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: launch.addingTimeInterval(hour)))
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: launch.addingTimeInterval(7 * hour)))
    }

    func testADeviceClockMovedBackDoesNotLockTheGateOut() {
        var gate = ForegroundRefreshGate(lastAttempt: now(agedBy: 10 * day))
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: 5 * day)), "an interval that cannot be measured does not block")
        XCTAssertEqual(gate.lastAttempt, now(agedBy: 5 * day))
    }

    func testTheThresholdAndIntervalCanBeChanged() {
        var gate = ForegroundRefreshGate()
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: 2 * hour), staleAfter: hour, minimumInterval: 30 * 60))
        XCTAssertFalse(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: 2 * hour + 60), staleAfter: hour, minimumInterval: 30 * 60))
        XCTAssertTrue(gate.shouldRefresh(generatedAt: generatedAt, now: now(agedBy: 2 * hour + 31 * 60), staleAfter: hour, minimumInterval: 30 * 60))
    }

    // MARK: The words

    func testTheSpanReadsInWholeDaysOrHours() {
        XCTAssertEqual(Presentation.span(day), "1 day")
        XCTAssertEqual(Presentation.span(3 * day), "3 days")
        XCTAssertEqual(Presentation.span(36 * hour), "36 hours")
        XCTAssertEqual(Presentation.span(hour), "1 hour")
        XCTAssertEqual(Presentation.span(6 * hour), "6 hours")
        XCTAssertEqual(Presentation.span(10), "1 hour", "never \"0 hours\"")
    }

    func testTheRuleIsBuiltFromTheConstants() {
        XCTAssertEqual(Presentation.returnRefreshRule, "while its data is more than 3 days old (at most once every 6 hours)")
    }

    func testTheOutOfDateBannerSaysWhenTheAppLooks() throws {
        let warning = try XCTUnwrap(Presentation.freshnessWarning(generatedAt: generatedAt, freshness: .stale(age: 4 * day)))
        XCTAssertTrue(
            warning.detail.hasSuffix("The app looks for new data each time it opens, and when you return to it \(Presentation.returnRefreshRule). Pull down on Search to look now."),
            warning.detail
        )
        XCTAssertFalse(warning.detail.contains("each time it opens;"), "the old sentence, which left out returning to the app")
        XCTAssertTrue(warning.spoken.hasPrefix("Warning. This data is out of date. "), "still opens with the warning")
    }

    // MARK: The privacy policy and the support page say it too

    private func page(_ name: String) throws -> String {
        try String(contentsOf: Repo.iosRoot.deletingLastPathComponent().appendingPathComponent("docs/site/\(name)"), encoding: .utf8)
    }

    /// What a page must say about when the app requests the file.
    static func problems(inPage text: String, name: String) -> [String] {
        var problems: [String] = []
        if !text.contains("when you return to \(name == "privacy.html" ? "the app" : "it") \(Presentation.returnRefreshRule)") {
            problems.append("\(name) does not say the app looks for data on return, with the same threshold and interval")
        }
        if text.contains("When you open the app, and when you pull to refresh") || text.contains("when you open it or pull to refresh") {
            problems.append("\(name) still gives only the old triggers")
        }
        return problems
    }

    func testThePrivacyPolicyAndTheSupportPageDescribeTheReturnRefresh() throws {
        for name in ["privacy.html", "support.html"] {
            XCTAssertEqual(Self.problems(inPage: try page(name), name: name), [])
        }
    }

    func testThePrivacyPolicyStillSaysTheAppCollectsNothing() throws {
        let privacy = try page("privacy.html")
        XCTAssertTrue(privacy.contains("collects nothing about you"))
        XCTAssertTrue(privacy.contains("no analytics, no crash reporting, no advertising, no tracking"))
        XCTAssertTrue(privacy.contains("no account, no cookie and no identifier created by the app"))
        let dated = try XCTUnwrap(privacy.range(of: #"Last updated (\d{4}-\d{2}-\d{2})\."#, options: .regularExpression), "the policy carries its date")
        XCTAssertGreaterThanOrEqual(String(privacy[dated].dropFirst("Last updated ".count).prefix(10)), "2026-09-19", "a changed policy carries a new date")
    }

    /// Negative control: the check fails on the old wording and on a page
    /// with different numbers.
    func testThePageCheckCanFail() throws {
        let privacy = try page("privacy.html")
        let old = privacy.replacingOccurrences(of: "when you return to the app \(Presentation.returnRefreshRule)", with: "and when you pull to refresh")
        XCTAssertNotEqual(old, privacy, "the sabotage landed")
        XCTAssertFalse(Self.problems(inPage: old, name: "privacy.html").isEmpty)
        let wrongNumbers = privacy.replacingOccurrences(of: "more than 3 days old", with: "more than 2 days old")
        XCTAssertNotEqual(wrongNumbers, privacy, "the sabotage landed")
        XCTAssertFalse(Self.problems(inPage: wrongNumbers, name: "privacy.html").isEmpty)
    }

    // MARK: The app is wired to it (source scan; CI runs `swift test`, not the UI tests)

    private func appSource(_ path: String) throws -> String {
        try String(contentsOf: Repo.iosRoot.appendingPathComponent("QueerTVGuide/\(path)"), encoding: .utf8)
    }

    static func wiringProblems(app: String, model: String, about: String) -> [String] {
        var problems: [String] = []
        if !app.contains("if phase == .active { Task { await model.refreshIfStaleOnReturn() } }") {
            problems.append("coming to the foreground does not call refreshIfStaleOnReturn")
        }
        if !model.contains("refreshGate.shouldRefresh(generatedAt: snapshot.generatedAt, now: clockReading)") {
            problems.append("refreshIfStaleOnReturn does not ask the gate")
        }
        if !model.contains("refreshGate.recordAttempt(at: now())") {
            problems.append("refresh() does not record its attempt, so launch and pull to refresh would not count toward the interval")
        }
        if !about.contains("\\(Presentation.returnRefreshRule)") {
            problems.append("About does not state the return refresh")
        }
        return problems
    }

    func testTheAppAsksTheGateOnReturnAndSaysSoOnAbout() throws {
        XCTAssertEqual(Self.wiringProblems(
            app: try appSource("App/QueerTVGuideApp.swift"),
            model: try appSource("App/AppModel.swift"),
            about: try appSource("Views/AboutView.swift")
        ), [])
    }

    func testTheWiringScanCanFail() throws {
        let app = try appSource("App/QueerTVGuideApp.swift")
        let model = try appSource("App/AppModel.swift")
        let about = try appSource("Views/AboutView.swift")
        let noCall = app.replacingOccurrences(of: "Task { await model.refreshIfStaleOnReturn() }", with: "model.readClock()")
        XCTAssertNotEqual(noCall, app, "the sabotage landed")
        XCTAssertEqual(Self.wiringProblems(app: noCall, model: model, about: about).count, 1)
        let noRecord = model.replacingOccurrences(of: "refreshGate.recordAttempt(at: now())", with: "")
        XCTAssertNotEqual(noRecord, model, "the sabotage landed")
        XCTAssertEqual(Self.wiringProblems(app: app, model: noRecord, about: about).count, 1)
    }

    /// A failed look on return is not an alert: the only place the app shows
    /// the last refresh error is the data footer's one line.
    func testARefreshErrorIsNeverShownAsAnAlert() throws {
        var readers: [String] = []
        for file in Repo.sourceFiles(extensions: ["swift"]) where file.path.contains("/ios/QueerTVGuide/Views/") {
            let text = try String(contentsOf: file, encoding: .utf8)
            if text.contains("lastRefreshError") { readers.append(file.lastPathComponent) }
            if text.contains("lastRefreshError"), text.contains(".alert(") || text.contains("confirmationDialog(") {
                XCTFail("\(file.lastPathComponent) reads lastRefreshError and shows an alert")
            }
        }
        XCTAssertEqual(readers, ["DataStatusFooter.swift"])
    }
}
