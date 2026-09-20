import Foundation
import XCTest
@testable import GuideCore

/// The credits each source requires (docs/LICENSES-AND-ATTRIBUTION.md,
/// DECISIONS 0012): what `Attribution` derives, whether the real bundled
/// snapshot carries everything the app links to, and whether the views
/// that show a source's data render its credit. The last is a source scan
/// because CI runs `swift test`, not the UI tests.
final class AttributionTests: XCTestCase {
    // Bare hosts, never "https://…" literals: SourceTreeGuardTests allows
    // no host but the snapshot's in ios/ source.
    static let lezWatchHost = "lezwatchtv.com"
    static let tvmazeHost = "www.tvmaze.com"
    static let ccBySA4Path = "/licenses/by-sa/4.0" // URL.path drops the trailing slash

    // MARK: Attribution (GuideCore)

    func testScheduleCreditLinksTheShowsTVmazePageAndTheLicense() throws {
        let s = try Repo.fixture()
        let show = try XCTUnwrap(s.show(id: "lwtv:show:101"))
        let credit = try XCTUnwrap(Attribution.tvmazeCredit(for: show.schedule, in: s))
        XCTAssertEqual(credit.source.url, show.schedule.tvmazeURL)
        XCTAssertEqual(credit.source.title, "Schedule data from TVmaze")
        XCTAssertEqual(credit.license.title, "CC BY-SA 4.0")
        XCTAssertEqual(credit.license.url.path, Self.ccBySA4Path)
    }

    func testNoScheduleMeansNoTVmazeDataAndNoCredit() throws {
        let s = try Repo.fixture()
        let unmatched = try XCTUnwrap(s.show(id: "lwtv:show:103"))
        XCTAssertFalse(unmatched.schedule.scheduleKnown)
        XCTAssertNil(Attribution.tvmazeCredit(for: unmatched.schedule, in: s))
    }

    func testGeneralCreditLinksTVmazeItself() throws {
        let s = try Repo.fixture()
        let credit = try XCTUnwrap(Attribution.tvmazeCredit(in: s))
        XCTAssertEqual(credit.source.url.host, Self.tvmazeHost)
        XCTAssertEqual(credit.source.url.path, "/")
    }

    func testASnapshotWithoutTVmazesEntryFailsToDecode() throws {
        let data = try JSONEdit.edit(try Repo.fixtureData()) { root in
            root["attribution"] = (root["attribution"] as! [[String: Any]]).filter { $0["source"] as? String != "tvmaze" }
        }
        XCTAssertThrowsError(try SnapshotDecoder().decode(data)) { error in
            XCTAssertTrue("\(error)".contains("missing attribution entry for tvmaze"), "unexpected error: \(error)")
        }
    }

    func testLezWatchLinkLabelNamesTheRecord() {
        XCTAssertEqual(Attribution.lezWatchLinkLabel(for: "Mara Quill"), "View Mara Quill on LezWatch.TV")
        XCTAssertTrue(Attribution.nonEndorsement.contains("LezWatch.TV"))
        XCTAssertTrue(Attribution.nonEndorsement.contains("TVmaze"))
        XCTAssertTrue(Attribution.nonEndorsement.contains("do not endorse this app"))
    }

    // MARK: The real bundled snapshot carries every link the app shows

    func testRealSnapshotGivesEveryRecordAndScheduleSomethingToLink() throws {
        guard let data = try? Data(contentsOf: Repo.bundledSnapshot) else {
            return XCTFail("\(Repo.bundledSnapshot.path) is missing: run `make -C ios bundle-snapshot`")
        }
        let s = try SnapshotDecoder().decode(data)
        let showsWithoutPage = s.shows.filter { $0.sourceURL.host != Self.lezWatchHost }
        let charactersWithoutPage = s.characters.filter { $0.sourceURL.host != Self.lezWatchHost }
        let schedulesWithoutCredit = s.shows.filter {
            $0.schedule.scheduleKnown && ($0.schedule.tvmazeURL?.host != Self.tvmazeHost || Attribution.tvmazeCredit(for: $0.schedule, in: s) == nil)
        }
        XCTAssertEqual(showsWithoutPage.map(\.id), [], "shows with no LezWatch.TV page to link")
        XCTAssertEqual(charactersWithoutPage.map(\.id), [], "characters with no LezWatch.TV page to link")
        XCTAssertEqual(schedulesWithoutCredit.map(\.id), [], "schedules shown without a TVmaze page to credit")

        let lw = try XCTUnwrap(s.attribution(for: Attribution.lezWatchSource))
        XCTAssertEqual(lw.url.host, Self.lezWatchHost)
        XCTAssertTrue(lw.text.contains("LezWatch.TV does not endorse this app"))
        let tv = try XCTUnwrap(s.attribution(for: Attribution.tvmazeSource))
        XCTAssertEqual(tv.url.host, Self.tvmazeHost)
        XCTAssertEqual(tv.licenseURL.path, Self.ccBySA4Path)
        for needle in ["CC BY-SA 4.0", "Reformatted", "without warranty", "does not endorse this app"] {
            XCTAssertTrue(tv.text.contains(needle), "TVmaze credit lacks \(needle)")
        }
        XCTAssertEqual(s.license.snapshot.spdx, "CC-BY-SA-4.0")
        XCTAssertTrue(s.license.notice.contains("LezWatch.TV") && s.license.notice.contains("TVmaze"))
    }

    // MARK: The views render the credits (source scan; CI-visible)

    struct Rule {
        let file: String
        let mustContain: [String]
        let why: String
    }

    static let rules: [Rule] = [
        Rule(file: "Views/ShowDetailView.swift", mustContain: ["LezWatchSourceLink(name: show.title, url: show.sourceURL)", "TVmazeCreditView(credit:"], why: "show screen: LezWatch.TV page link, TVmaze credit with the schedule"),
        Rule(file: "Views/CharacterDetailView.swift", mustContain: ["LezWatchSourceLink(name: character.name, url: character.sourceURL)"], why: "character screen: LezWatch.TV page link"),
        Rule(file: "Views/FavoritesView.swift", mustContain: ["TVmazeCreditView(credit:"], why: "favorites show TVmaze next episodes"),
        Rule(file: "Views/AboutView.swift", mustContain: ["Attribution.nonEndorsement", "openURL(item.url)", "openURL(item.licenseURL)", "Text(item.text)", "snapshot.license.notice"], why: "About: sources named and linked, licenses linked, non-endorsement"),
    ]

    /// Any view that shows TVmaze data must also render TVmaze's credit.
    static let tvmazeDataMarkers = ["Presentation.nextEpisode(", ".nextEpisode", ".previousEpisode"]

    static func violations(in text: String, rule: Rule) -> [String] {
        rule.mustContain.filter { !text.contains($0) }.map { "\(rule.file) lacks \($0) (\(rule.why))" }
    }

    func testEveryScreenRendersTheCreditsItsDataRequires() throws {
        let app = Repo.iosRoot.appendingPathComponent("QueerTVGuide")
        var problems: [String] = []
        for rule in Self.rules {
            let text = try String(contentsOf: app.appendingPathComponent(rule.file), encoding: .utf8)
            problems += Self.violations(in: text, rule: rule)
        }
        for file in Repo.sourceFiles(extensions: ["swift"]) where file.path.contains("/QueerTVGuide/Views/") {
            let text = try String(contentsOf: file, encoding: .utf8)
            if Self.tvmazeDataMarkers.contains(where: text.contains), !text.contains("TVmazeCreditView(") {
                problems.append("\(file.lastPathComponent) shows TVmaze data without TVmazeCreditView")
            }
        }
        XCTAssertEqual(problems, [])
    }

    /// Negative control: the scan really fails when a credit is removed.
    func testTheScanCatchesARemovedCredit() throws {
        let rule = Self.rules[0]
        let text = try String(contentsOf: Repo.iosRoot.appendingPathComponent("QueerTVGuide/\(rule.file)"), encoding: .utf8)
        let sabotaged = text.replacingOccurrences(of: "LezWatchSourceLink(name: show.title, url: show.sourceURL)", with: "EmptyView()")
        XCTAssertNotEqual(sabotaged, text, "the sabotage landed")
        XCTAssertEqual(Self.violations(in: sabotaged, rule: rule).count, 1)
    }
}
