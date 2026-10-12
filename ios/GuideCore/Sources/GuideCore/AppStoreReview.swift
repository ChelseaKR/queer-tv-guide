import Foundation

/// The App Store's "write a review" page for this app, behind the "Rate"
/// row in About. The app never fetches it: the row hands it to the system
/// `openURL`, and iOS opens the App Store app on the review sheet. Nothing
/// is sent by this process, nothing is offered in return for a rating, and
/// the row is shown to everyone the same way, whatever they think of the
/// app (App Review guideline 5.6.1).
///
/// This is the one host besides the snapshot's that may appear in `ios/`,
/// and only in this file (`SourceTreeGuardTests`).
public enum AppStoreReview {
    /// The app's Apple ID in App Store Connect. The pipeline's site badge
    /// uses the same number (`pipeline/src/qtv_pipeline/app_store.py`), and
    /// `AppStoreReviewTests` checks the two agree.
    public static let appID = "6818637465"

    /// Apple's documented deep link to the review sheet: the product page
    /// with `action=write-review`.
    public static let writeReviewURL = URL(string: "https://apps.apple.com/app/id6818637465?action=write-review")!
}
