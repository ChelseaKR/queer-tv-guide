import Foundation
import XCTest
@testable import GuideCore

/// The app ships `QueerTVGuide/Resources/snapshot.v1.json` as its
/// first-launch and offline catalog, so it is what a user sees before the
/// one refresh GET ever succeeds. It must be real, pipeline-published
/// LezWatch.TV + TVmaze data — never the hand-made fixture, whose invented
/// shows would be presented as real ones. `make bundle-snapshot` puts it
/// there; these tests re-check it on every `swift test` (and so in CI).
final class BundledSnapshotTests: XCTestCase {
    /// The real catalog is ~2,300 shows / ~7,400 characters (2026-09). The
    /// floor is far below that on purpose: it only has to catch a fixture or
    /// a truncated file, not track the source's size.
    static let minimumShows = 1_000
    static let minimumCharacters = 1_000

    /// Every reason `data` must not ship as the bundled snapshot. Empty means
    /// shippable.
    static func shippabilityProblems(_ data: Data) -> [String] {
        var problems: [String] = []

        guard let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return ["not a JSON object"]
        }
        let build = root["build"] as? [String: Any]
        let pipelineVersion = build?["pipeline_version"] as? String ?? ""
        let run = build?["run"] as? [String: Any]
        if pipelineVersion.isEmpty {
            problems.append("build.pipeline_version is missing")
        } else if pipelineVersion.localizedCaseInsensitiveContains("fixture") {
            problems.append("build.pipeline_version \"\(pipelineVersion)\" is a fixture")
        }
        if (run?["workflow_run_id"] as? String)?.isEmpty ?? true {
            problems.append("build.run.workflow_run_id is empty: not published by the nightly workflow")
        }
        if (run?["git_sha"] as? String)?.isEmpty ?? true {
            problems.append("build.run.git_sha is empty")
        }
        let notice = (root["licence"] as? [String: Any])?["notice"] as? String ?? ""
        if notice.localizedCaseInsensitiveContains("fixture") {
            problems.append("licence.notice describes a fixture")
        }

        let snapshot: Snapshot
        do {
            snapshot = try SnapshotDecoder().decode(data)
        } catch {
            problems.append("does not decode with the app's decoder: \(error.localizedDescription)")
            return problems
        }
        if snapshot.shows.count < minimumShows {
            problems.append("\(snapshot.shows.count) shows, below the real-catalog floor of \(minimumShows)")
        }
        if snapshot.characters.count < minimumCharacters {
            problems.append("\(snapshot.characters.count) characters, below the real-catalog floor of \(minimumCharacters)")
        }
        if snapshot.license.snapshot.spdx != "CC-BY-SA-4.0" {
            problems.append("licence.snapshot.spdx is \(snapshot.license.snapshot.spdx), not CC-BY-SA-4.0")
        }
        let sources = Set(snapshot.attribution.map(\.source))
        if sources != ["lezwatch", "tvmaze"] {
            problems.append("attribution sources are \(sources.sorted()), expected lezwatch + tvmaze")
        }
        return problems
    }

    func testBundledSnapshotIsRealPublishedData() throws {
        // Gitignored and fetched, never committed: a missing file is a
        // failure with a way out, not a skip.
        guard let data = try? Data(contentsOf: Repo.bundledSnapshot) else {
            return XCTFail("\(Repo.bundledSnapshot.path) is missing: run `make -C ios bundle-snapshot`")
        }
        XCTAssertEqual(Self.shippabilityProblems(data), [])
    }

    // MARK: negative controls: the check is not vacuous

    func testTheFixtureIsRefused() throws {
        let problems = Self.shippabilityProblems(try Repo.fixtureData())
        XCTAssertTrue(problems.contains { $0.contains("is a fixture") }, "\(problems)")
        XCTAssertTrue(problems.contains { $0.contains("workflow_run_id") }, "\(problems)")
        XCTAssertTrue(problems.contains { $0.contains("below the real-catalog floor") }, "\(problems)")
    }

    func testALocallyBuiltSnapshotIsRefused() throws {
        // Same real bytes, but as `qtv build` writes them outside CI: no run id.
        let data = try JSONEdit.edit(try Data(contentsOf: Repo.bundledSnapshot)) { root in
            var build = root["build"] as! [String: Any]
            build["run"] = ["git_sha": NSNull(), "workflow_run_id": NSNull()]
            root["build"] = build
        }
        let problems = Self.shippabilityProblems(data)
        XCTAssertTrue(problems.contains { $0.contains("workflow_run_id") }, "\(problems)")
    }
}
