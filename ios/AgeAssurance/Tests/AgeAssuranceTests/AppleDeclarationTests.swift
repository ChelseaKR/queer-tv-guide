#if canImport(DeclaredAgeRange)
import DeclaredAgeRange
import XCTest
@testable import AgeAssurance

/// Apple's declaration values, as the real DeclaredAgeRange framework spells
/// them, mapped to the package's. These need a 26.2 or later OS to run
/// (`confirmed` needs 26.5); on an older one they skip and say why. The iOS
/// app's own unit tests (QueerTVGuideTests/AgeAssuranceDeclarationTests)
/// run the `confirmed` case again on the iOS 26.5 simulator.
final class AppleDeclarationTests: XCTestCase {
    func testConfirmedIsConfirmed() throws {
        guard #available(iOS 26.5, macOS 26.5, *) else {
            throw XCTSkip("AgeRangeDeclaration.confirmed needs an iOS or macOS 26.5 runtime")
        }
        XCTAssertEqual(AgeDeclaration(apple: .confirmed), .confirmed)
    }

    /// The values iOS 26.2 to 26.4 report instead of `confirmed`. Deprecated
    /// in the 26.5 SDK, so naming them here warns; that is expected.
    func testCheckedValuesBeforeConfirmedAreConfirmed() throws {
        guard #available(iOS 26.2, macOS 26.2, *) else {
            throw XCTSkip("the checked AgeRangeDeclaration values need a 26.2 runtime")
        }
        let checked: [AgeRangeService.AgeRangeDeclaration] = [
            .paymentChecked, .guardianPaymentChecked,
            .governmentIDChecked, .guardianGovernmentIDChecked,
            .checkedByOtherMethod, .guardianCheckedByOtherMethod,
        ]
        for value in checked {
            XCTAssertEqual(AgeDeclaration(apple: value), .confirmed, "\(value)")
        }
    }

    func testSelfAndGuardianKeepTheirMeaning() throws {
        guard #available(iOS 26.2, macOS 26.2, *) else {
            throw XCTSkip("AgeRangeDeclaration needs a 26.2 runtime")
        }
        XCTAssertEqual(AgeDeclaration(apple: .selfDeclared), .selfDeclared)
        XCTAssertEqual(AgeDeclaration(apple: .guardianDeclared), .guardianDeclared)
    }

    func testNoDeclarationIsUnspecifiedNotConfirmed() throws {
        guard #available(iOS 26.2, macOS 26.2, *) else {
            throw XCTSkip("AgeRangeDeclaration needs a 26.2 runtime")
        }
        XCTAssertEqual(AgeDeclaration(apple: nil), .unspecified)
    }

    /// A `confirmed` adult range is still read by its bounds, like any other:
    /// the declaration never makes a range an adult on its own.
    func testConfirmedDoesNotOverrideTheRange() throws {
        guard #available(iOS 26.5, macOS 26.5, *) else {
            throw XCTSkip("AgeRangeDeclaration.confirmed needs an iOS or macOS 26.5 runtime")
        }
        let declaration = AgeDeclaration(apple: .confirmed)
        XCTAssertEqual(AgeSignal.from(lowerBound: 18, upperBound: nil, declaration: declaration), .known(.adult, .confirmed))
        XCTAssertEqual(AgeSignal.from(lowerBound: 13, upperBound: 15, declaration: declaration), .known(.age13to15, .confirmed))
        XCTAssertFalse(AgeSignal.from(lowerBound: nil, upperBound: nil, declaration: declaration).isKnownAdult)
    }
}
#endif
