import Foundation
import XCTest
@testable import GuideCore

/// `Episode.airInstant`: a time only when TVmaze records an air time. The
/// values are the real ones quoted in issue #56 (2026-09-19 snapshot).
final class EpisodeAirTimeTests: XCTestCase {
    private func episode(airdate: String?, airtime: String?, airstamp: String?) -> Episode {
        Episode(tvmazeID: 1, season: 1, number: 1, name: nil, airdate: airdate, airtime: airtime, airstamp: airstamp, runtime: nil, url: URL(fileURLWithPath: "/episodes/1"))
    }

    private func date(_ iso: String) -> Date {
        ISO8601DateFormatter().date(from: iso)!
    }

    /// 11 of the 49 next episodes carry `airtime: null` and a placeholder
    /// `airstamp`: none of them is a time.
    func testAPlaceholderAirstampIsNotATime() {
        XCTAssertNil(episode(airdate: "2026-09-21", airtime: nil, airstamp: "2026-09-21T16:00:00+00:00").airInstant, "Days of Our Lives")
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: nil, airstamp: "2026-09-23T12:00:00+00:00").airInstant, "Ted Lasso")
        XCTAssertNil(episode(airdate: "2026-10-14", airtime: nil, airstamp: "2026-10-14T12:00:00+00:00").airInstant, "Helluva Boss")
    }

    /// The negative control: the same stamp with a recorded air time is a
    /// time, so `airtime` is the only thing that decides it.
    func testARecordedAirTimeMakesTheAirstampAnInstant() {
        XCTAssertEqual(episode(airdate: "2026-10-15", airtime: "22:00", airstamp: "2026-10-16T02:00:00+00:00").airInstant, date("2026-10-16T02:00:00Z"), "Grey's Anatomy")
        XCTAssertEqual(episode(airdate: "2026-09-23", airtime: "12:00", airstamp: "2026-09-23T12:00:00+00:00").airInstant, date("2026-09-23T12:00:00Z"), "the same stamp as Ted Lasso's, with a time")
    }

    func testAnEmptyOrBlankAirTimeIsNoAirTime() {
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: "", airstamp: "2026-09-23T12:00:00+00:00").airInstant)
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: "  ", airstamp: "2026-09-23T12:00:00+00:00").airInstant)
    }

    func testNoStampOrAnUnreadableOneIsNoInstant() {
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: "12:00", airstamp: nil).airInstant)
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: "12:00", airstamp: "not a date").airInstant)
        XCTAssertNil(episode(airdate: "2026-09-23", airtime: "12:00", airstamp: "2026-09-23").airInstant)
    }

    /// The offset in the stamp is honored: the same instant written in two
    /// zones is one `Date`.
    func testTheStampsOffsetIsHonored() {
        let a = episode(airdate: "2026-09-20", airtime: "21:00", airstamp: "2026-09-20T21:00:00-04:00").airInstant
        let b = episode(airdate: "2026-09-21", airtime: "01:00", airstamp: "2026-09-21T01:00:00+00:00").airInstant
        XCTAssertEqual(a, b)
        XCTAssertNotNil(a)
    }

    /// Nothing outside `airInstant` reads `airstamp`: a time shown or
    /// scheduled from a placeholder would be a made-up time. Comments are
    /// not code.
    func testOnlyAirInstantReadsTheAirstamp() throws {
        let root = Repo.iosRoot
        let access = try NSRegularExpression(pattern: #"\.airstamp\b|\bairstamp\s*:"#)
        var readers: [String] = []
        for file in Repo.sourceFiles(extensions: ["swift"]) where !file.path.contains("Tests/") && !file.path.contains("/QueerTVGuideUITests/") {
            // The model that declares the field and `airInstant`.
            if file.lastPathComponent == "Snapshot.swift" { continue }
            let code = try String(contentsOf: file, encoding: .utf8)
                .split(separator: "\n", omittingEmptySubsequences: false)
                .filter { !$0.trimmingCharacters(in: .whitespaces).hasPrefix("//") }
                .joined(separator: "\n")
            if access.firstMatch(in: code, range: NSRange(code.startIndex..., in: code)) != nil {
                readers.append(file.path.replacingOccurrences(of: root.path + "/", with: ""))
            }
        }
        XCTAssertEqual(readers, [], "these read airstamp directly; use Episode.airInstant")
    }
}
