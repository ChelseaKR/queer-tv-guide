import SwiftUI

/// A tab's navigation, shaped to the space it has (DECISIONS 0016).
///
/// Compact width (iPhone, or an iPad app in a narrow Split View or Slide
/// Over): one stack, as before. Regular width (iPad full screen, a wide
/// split, a Mac window): a split view, the list in a sidebar column and
/// whatever it opens in the detail column beside it, so a 13-inch screen
/// shows the list and a show at once instead of a phone list stretched
/// edge to edge.
struct AdaptiveNavigation<List: View>: View {
    let placeholderTitle: String
    let placeholderSystemImage: String
    let placeholderMessage: String
    @ViewBuilder let list: () -> List

    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        if horizontalSizeClass == .regular {
            NavigationSplitView {
                list()
                    .navigationSplitViewColumnWidth(min: 320, ideal: 400, max: 480)
            } detail: {
                NavigationStack {
                    EmptyState(title: placeholderTitle, systemImage: placeholderSystemImage, message: placeholderMessage)
                }
            }
            .navigationSplitViewStyle(.balanced)
        } else {
            NavigationStack {
                list()
            }
        }
    }
}

/// The widest a column of reading text gets: about 70 characters of body
/// text. Wider screens center it with margins, so lines stay readable.
enum ReadableWidth {
    static let maximum: CGFloat = 720
}

extension View {
    /// Centers content no wider than `ReadableWidth.maximum`, for a scroll
    /// view's stack of text (show and character screens, the first-run
    /// pages). On an iPhone it changes nothing: the screen is narrower.
    func readableWidth() -> some View {
        frame(maxWidth: ReadableWidth.maximum)
            .frame(maxWidth: .infinity)
    }

    /// The same for a `List`: its rows keep the readable width, centered,
    /// with the list's own background running edge to edge.
    func readableListWidth() -> some View {
        modifier(ReadableListWidth())
    }
}

private struct ReadableListWidth: ViewModifier {
    func body(content: Content) -> some View {
        GeometryReader { proxy in
            let margin = max(0, (proxy.size.width - ReadableWidth.maximum) / 2)
            content.contentMargins(.horizontal, margin, for: .scrollContent)
        }
    }
}
