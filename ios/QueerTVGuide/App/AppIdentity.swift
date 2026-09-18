import Foundation

/// The product's human-facing name (DECISIONS 0006). This is the
/// one Swift source location it is spelled out; the home-screen name is
/// `INFOPLIST_KEY_CFBundleDisplayName` in `ios/Config/Product.xcconfig`, and
/// `SourceTreeGuardTests` checks the two agree. The repository, bundle id,
/// `PRODUCT_NAME` and targets keep their working names on purpose.
enum AppIdentity {
    static let displayName = "Queer Frame"
}
