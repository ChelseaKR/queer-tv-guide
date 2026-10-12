import XCTest
@testable import GuideCore

final class RefreshProblemTests: XCTestCase {
    func testNoConnectionIsOffline() {
        for code: URLError.Code in [.notConnectedToInternet, .networkConnectionLost, .dataNotAllowed, .internationalRoamingOff] {
            XCTAssertTrue(RefreshProblem.isOffline(URLError(code)), "\(code)")
        }
        XCTAssertEqual(RefreshProblem(SnapshotRefresher.RefreshError.transport("x", offline: true)), .offline)
    }

    func testConnectedButNoAnswerIsUnreachable() {
        for code: URLError.Code in [.timedOut, .cannotFindHost, .cannotConnectToHost, .dnsLookupFailed, .secureConnectionFailed] {
            XCTAssertFalse(RefreshProblem.isOffline(URLError(code)), "\(code)")
        }
        XCTAssertEqual(RefreshProblem(SnapshotRefresher.RefreshError.transport("x", offline: false)), .unreachable)
        XCTAssertEqual(RefreshProblem(SnapshotRefresher.RefreshError.httpStatus(503)), .unreachable)
        XCTAssertEqual(RefreshProblem(SnapshotRefresher.RefreshError.notHTTP), .unreachable)
    }

    func testAFileThatFailsItsChecksIsUnusable() {
        XCTAssertEqual(RefreshProblem(SnapshotRefresher.RefreshError.rejected("bad")), .unusable)
    }

    func testAnUnknownErrorIsUnreachableNotOffline() {
        struct Other: Error {}
        XCTAssertEqual(RefreshProblem(Other()), .unreachable)
    }

    /// Every message keeps the promise that nothing on screen was lost,
    /// and none of them passes a raw system error through.
    func testEveryMessageSaysTheDataStays() {
        for problem: RefreshProblem in [.offline, .unreachable, .unusable] {
            XCTAssertTrue(problem.message.hasSuffix("The data on screen stays as it is."), problem.message)
            XCTAssertFalse(problem.message.contains("HTTP"), problem.message)
            XCTAssertFalse(problem.message.contains("iPhone"), "the app also runs on iPad in compatibility mode")
        }
    }

    /// End to end through the refresher: the stub's default failure is
    /// notConnectedToInternet, which must read as offline.
    func testTheRefresherMarksNoConnectionAsOffline() async throws {
        let dir = try Repo.temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: dir) }
        StubURLProtocol.reset()
        defer { StubURLProtocol.reset() }
        let refresher = SnapshotRefresher(store: SnapshotStore(directory: dir, bundledURL: Repo.fixtureURL), protocolClasses: [StubURLProtocol.self])
        do {
            _ = try await refresher.refresh()
            XCTFail("expected an error")
        } catch {
            XCTAssertEqual(RefreshProblem(error), .offline, "\(error)")
        }
    }
}
