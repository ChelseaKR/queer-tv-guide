import AgeAssurance
import DeclaredAgeRange
import XCTest

/// iOS 26.5 reports `confirmed` for an age range Apple checked, in place of
/// the payment, ID and other "checked" values of iOS 26.2 to 26.4. The
/// AgeAssurance package's own tests cover the mapping on macOS; this runs it
/// in the app's simulator, on the iOS the app is built and tested against
/// (ios/Makefile: iPhone 17 Pro, iOS 26.5).
final class AgeAssuranceDeclarationTests: XCTestCase {
    func testConfirmedOnIOS26_5IsConfirmed() throws {
        guard #available(iOS 26.5, *) else {
            throw XCTSkip("AgeRangeDeclaration.confirmed needs iOS 26.5")
        }
        XCTAssertEqual(AgeDeclaration(apple: .confirmed), .confirmed)
        XCTAssertEqual(
            AgeSignal.from(lowerBound: 18, upperBound: nil, declaration: AgeDeclaration(apple: .confirmed)),
            .known(.adult, .confirmed)
        )
    }

    func testSelfDeclaredStaysSelfDeclared() throws {
        guard #available(iOS 26.2, *) else {
            throw XCTSkip("AgeRangeDeclaration needs iOS 26.2")
        }
        XCTAssertEqual(AgeDeclaration(apple: .selfDeclared), .selfDeclared)
        XCTAssertEqual(AgeDeclaration(apple: nil), .unspecified)
    }
}
