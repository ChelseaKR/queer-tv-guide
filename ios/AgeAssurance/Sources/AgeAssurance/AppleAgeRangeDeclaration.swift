// How Apple's `AgeRangeDeclaration` maps onto the package's `AgeDeclaration`.
// Kept apart from DeclaredAgeRangePlatform.swift (which needs UIKit) so the
// mapping also compiles for macOS, where `swift test` can check it: the
// DeclaredAgeRange framework ships in the macOS 26 SDK too.
//
// iOS 26.5 reports `confirmed` for any range Apple checked, in place of the
// six "checked" values iOS 26.2 to 26.4 report (`paymentChecked`,
// `governmentIDChecked`, `checkedByOtherMethod` and their guardian forms,
// deprecated in the 26.5 SDK and renamed to `confirmed`). Every one of them
// maps to `.confirmed`. The `default` branch is what does it, so a value Apple
// adds later reads as "checked by the platform", not as self-declared; the
// tests name `confirmed` explicitly.

#if canImport(DeclaredAgeRange)
import DeclaredAgeRange

extension AgeDeclaration {
    /// The package's declaration for Apple's. No declaration at all is
    /// `.unspecified`, never a guess.
    @available(iOS 26.2, macOS 26.2, *)
    @available(visionOS, unavailable)
    public init(apple value: AgeRangeService.AgeRangeDeclaration?) {
        guard let value else {
            self = .unspecified
            return
        }
        switch value {
        case .selfDeclared:
            self = .selfDeclared
        case .guardianDeclared:
            self = .guardianDeclared
        default:
            // `confirmed` (iOS 26.5 and later) and the checked values it
            // replaced (iOS 26.2 to 26.4).
            self = .confirmed
        }
    }
}
#endif
