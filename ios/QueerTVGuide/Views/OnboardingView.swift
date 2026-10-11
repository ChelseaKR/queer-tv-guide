import SwiftUI
import GuideCore

/// The first-run screen: a short native pager. A welcome page, then one
/// page each on how spoilers are kept closed, what "not recorded" means,
/// where the data comes from, and what the app does not collect.
///
/// Built so the pager costs nothing in accessibility (it replaced a single
/// scrolling page that was chosen for exactly these reasons):
/// - Next and Back are real buttons, so nobody needs the swipe. A swipe
///   works too, and each change of page is a light selection tap.
/// - Each page is its own scroll view, so it reflows at every text size,
///   AX5 included, and the buttons stack at accessibility sizes.
/// - VoiceOver hears "Page 2 of 5", and focus moves to the new page's
///   heading after Next or Back, so the page is read from its top.
/// - Reduce Motion: pages change without the slide, and the symbols do
///   not bounce.
///
/// Skippable from the first moment; About opens it again.
struct OnboardingView: View {
    /// Called by "Start browsing" and "Skip" on first run, and "Done" or
    /// "Close" when opened again from About.
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
            title: "Nothing about you leaves this device",
            body: "No account, no analytics, no tracking. Favorites stay on this device. The app downloads one data file, the same file for everyone."
        ),
    ]

    /// The welcome page is page 0; the points follow.
    static var pageCount: Int { points.count + 1 }

    @State private var page = 0
    @AccessibilityFocusState private var focusedPage: Int?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    private var isLastPage: Bool { page == Self.pageCount - 1 }

    var body: some View {
        VStack(spacing: 0) {
            topBar
            TabView(selection: $page) {
                OnboardingPage(
                    systemImage: "sparkles.tv",
                    title: "Welcome to \(AppIdentity.displayName)",
                    message: "A spoiler-safe guide to queer characters on TV. Here is how it works, in four short pages.",
                    identifier: "onboarding-welcome",
                    isCurrent: page == 0,
                    focus: $focusedPage,
                    index: 0
                )
                .tag(0)
                ForEach(Array(Self.points.enumerated()), id: \.element.id) { offset, point in
                    OnboardingPage(
                        systemImage: point.systemImage,
                        title: point.title,
                        message: point.body,
                        identifier: "onboarding-point-\(point.id)",
                        isCurrent: page == offset + 1,
                        focus: $focusedPage,
                        index: offset + 1
                    )
                    .tag(offset + 1)
                }
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            bottomBar
        }
        .background(Color(uiColor: .systemBackground))
        .sensoryFeedback(.selection, trigger: page)
        // After Next, Back or a swipe, VoiceOver starts the new page at its
        // heading instead of staying on the button.
        .onChange(of: page) { _, newPage in focusedPage = newPage }
    }

    private func go(to newPage: Int) {
        let target = min(max(newPage, 0), Self.pageCount - 1)
        withAnimation(reduceMotion ? nil : .snappy) { page = target }
    }

    @ViewBuilder
    private var topBar: some View {
        HStack {
            Spacer()
            // In the page, not a toolbar: Xcode's audit reports a toolbar
            // text button as not scaling with Dynamic Type.
            Button(isFirstRun ? "Skip" : "Close", action: finish)
                .font(.body.weight(.semibold))
                .frame(minHeight: 44)
                .contentShape(Rectangle())
                .accessibilityHint(isFirstRun ? "Starts browsing. About shows this again." : "Goes back to About.")
                .accessibilityIdentifier("onboarding-skip")
        }
        .padding(.horizontal)
        // Shown on the last page too, so the corner never jumps; there,
        // "Start browsing" below does the same thing.
        .opacity(isLastPage && isFirstRun ? 0 : 1)
        .accessibilityHidden(isLastPage && isFirstRun)
    }

    private var bottomBar: some View {
        VStack(spacing: 14) {
            PageIndicator(count: Self.pageCount, current: page)
            let layout = dynamicTypeSize.isAccessibilitySize
                ? AnyLayout(VStackLayout(spacing: 10))
                : AnyLayout(HStackLayout(spacing: 12))
            layout {
                if page > 0 {
                    Button {
                        go(to: page - 1)
                    } label: {
                        Text("Back")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                    .accessibilityIdentifier("onboarding-back")
                }
                if isLastPage {
                    Button(action: finish) {
                        Text(isFirstRun ? "Start browsing" : "Done")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .accessibilityIdentifier("onboarding-finish")
                } else {
                    Button {
                        go(to: page + 1)
                    } label: {
                        Text("Next")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .accessibilityIdentifier("onboarding-next")
                }
            }
        }
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity)
        .padding(.horizontal)
        .padding(.top, 8)
        .padding(.bottom, 12)
    }
}

/// One page: a large symbol in a tinted disc, a heading, and its text, in
/// its own scroll view so it reflows at every text size.
private struct OnboardingPage: View {
    let systemImage: String
    let title: String
    let message: String
    let identifier: String
    let isCurrent: Bool
    var focus: AccessibilityFocusState<Int?>.Binding
    let index: Int

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        // Centered while the text is short enough to read that way; at
        // accessibility sizes a paragraph reads better from the left.
        let alignment: TextAlignment = dynamicTypeSize.isAccessibilitySize ? .leading : .center
        GeometryReader { proxy in
        ScrollView {
            VStack(spacing: 24) {
                Image(systemName: systemImage)
                    .font(.system(size: 56, weight: .regular))
                    .foregroundStyle(.accessibleAccent)
                    .symbolEffect(.bounce, options: .nonRepeating, value: reduceMotion ? false : isCurrent)
                    .frame(width: 120, height: 120)
                    .background(Circle().fill(Color.accessibleAccent.opacity(0.12)))
                    .accessibilityHidden(true)
                VStack(alignment: dynamicTypeSize.isAccessibilitySize ? .leading : .center, spacing: 12) {
                    Text(title)
                        .font(.title.bold())
                        .multilineTextAlignment(alignment)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                        .accessibilityIdentifier(identifier)
                        .accessibilityFocused(focus, equals: index)
                    Text(message)
                        .font(.body)
                        .foregroundStyle(.subdued)
                        .multilineTextAlignment(alignment)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: dynamicTypeSize.isAccessibilitySize ? .leading : .center)
            }
            // A column, not a banner, on iPad and Mac.
            .frame(maxWidth: 560)
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 24)
            .padding(.bottom, 24)
            // Centered in the page while it fits; taller than the page (large
            // text), it starts at the top and scrolls.
            .frame(minHeight: proxy.size.height)
        }
        .scrollBounceBehavior(.basedOnSize)
        }
    }
}

/// Dots for sighted readers; one "Page 2 of 5" element for VoiceOver.
private struct PageIndicator: View {
    let count: Int
    let current: Int

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<count, id: \.self) { index in
                Capsule()
                    .fill(index == current ? Color.accessibleAccent : Color.subdued.opacity(0.35))
                    .frame(width: index == current ? 22 : 8, height: 8)
            }
        }
        .animation(reduceMotion ? nil : .snappy, value: current)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Page \(current + 1) of \(count)")
        .accessibilityIdentifier("onboarding-page-indicator")
    }
}
