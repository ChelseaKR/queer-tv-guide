import Foundation

/// The product's human-facing display name. The name is undecided
/// (DECISIONS 0004); this is the ONE place the placeholder is spelled out,
/// so the eventual rename is a one-line edit here (plus renaming
/// `PRODUCT_NAME` in `ios/Config/Product.xcconfig`, which is a clean
/// technical identifier on purpose — see the comment there). Never
/// Never the name DECISIONS 0004 rejects (it collides with an existing
/// messaging app).
enum AppIdentity {
    static let displayName = "Queer TV Guide"
}
