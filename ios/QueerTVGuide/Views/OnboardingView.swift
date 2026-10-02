import SwiftUI
import GuideCore

/// The first-run screen: how spoilers are kept closed, what "not recorded"
/// means, where the data comes from, and what the app does not collect. One
/// short scrolling page rather than a carousel, so VoiceOver reads it top to
/// bottom, it reflows at every text size, and there is nothing to animate.
/// Skippable from the first moment; About opens it again.
struct OnboardingView: View {
    /// Called by "Start browsing" and "Skip" on first run, and "Done" when
    /// opened again from About.
    let finish: () -> Void
    var isFirstRun = true

    /// UserDefaults key for "the first-run screen has been seen". UI tests
    /// pass `-onboarding.v1.seen YES` to start on Search, or `NO` to see it.
    static let seenKey = "onboarding.v1.seen"

    struct Point: Identifiable {
        let id: String
        let systemImage: String
        let title: String
        let body: String
    }

    static let points: [Point] = [
        Point(
            id: "spoilers",
            systemImage: "eye.slash",
            title: "Spoilers stay closed",
            body: "Whether a character dies is behind a Reveal button on every show and character. Until you open it, nothing on the screen gives the answer away, and VoiceOver cannot read it either. Plot notes stay folded too."
        ),
        Point(
            id: "not-recorded",
            systemImage: "questionmark.circle",
            title: "“Not recorded” is not “no”",
            body: "LezWatch.TV records deaths, not survival. When no death is recorded, the app says “Not recorded”. It never tells you a character lives."
        ),
        Point(
            id: "sources",
            systemImage: "books.vertical",
            title: "Where the data comes from",
            body: "Shows, characters and ratings come from LezWatch.TV, a community-run database. Episode schedules come from TVmaze, under CC BY-SA 4.0. Every show and character links back to its LezWatch.TV page. \(Attribution.nonEndorsement)"
        ),
        Point(
            id: "privacy",
            systemImage: "lock.shield",
            title: "Nothing about you leaves this phone",
            body: "No account, no analytics, no tracking. Favorites stay on this device. The app downloads one data file, the same file for everyone."
        ),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    // In the page, not the toolbar: Xcode's audit reports a
                    // toolbar text button as not scaling with Dynamic Type.
                    if isFirstRun {
                        HStack {
                            Spacer()
                            Button("Skip", action: finish)
                                .font(.body.weight(.semibold))
                                .frame(minHeight: 44)
                                .contentShape(Rectangle())
                                .accessibilityHint("Starts browsing. About shows this again.")
                        }
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Welcome to \(AppIdentity.displayName)")
                            .font(.largeTitle.bold())
                            .accessibilityAddTraits(.isHeader)
                        Text("A spoiler-safe guide to queer characters on TV.")
                            .font(.title3)
                            .foregroundStyle(.subdued)
                    }
                    ForEach(Self.points) { point in
                        OnboardingPoint(point: point)
                    }
                    Button(action: finish) {
                        Text(isFirstRun ? "Start browsing" : "Done")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .accessibilityIdentifier("onboarding-finish")
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            // This page has no navigation bar, so scrolled text ran up under
            // the status bar and was drawn across the clock (and the
            // accessibility audit could not finish measuring it). An opaque
            // strip of the page's own background covers the status bar.
            .overlay(alignment: .top) {
                GeometryReader { proxy in
                    Color(uiColor: .systemBackground)
                        .frame(height: proxy.safeAreaInsets.top)
                        .ignoresSafeArea(edges: .top)
                }
                .allowsHitTesting(false)
                .accessibilityHidden(true)
            }
        }
    }
}

private struct OnboardingPoint: View {
    let point: OnboardingView.Point

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 14) {
            Image(systemName: point.systemImage)
                .font(.title2)
                .foregroundStyle(.accessibleAccent)
                .frame(minWidth: 32)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 6) {
                // A heading VoiceOver's rotor can jump between, then its
                // text; the icon is decoration.
                Text(point.title)
                    .font(.headline)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("onboarding-point-\(point.id)")
                Text(point.body)
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
