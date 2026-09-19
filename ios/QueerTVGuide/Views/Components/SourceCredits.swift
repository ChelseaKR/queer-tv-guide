import SwiftUI
import GuideCore

/// A record's link back to its LezWatch.TV page. LezWatch.TV's terms ask
/// every reuse to "link back to us, or note us by name"; every show and
/// character screen carries one (SourceTreeGuardTests and the UI tests
/// fail if it goes).
struct LezWatchSourceLink: View {
    let name: String
    let url: URL

    @Environment(\.openURL) private var openURL

    var body: some View {
        Button {
            openURL(url)
        } label: {
            Label(Attribution.lezWatchLinkTitle, systemImage: "arrow.up.forward.square")
                .font(.subheadline)
        }
        .frame(minHeight: 44, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityLabel(Attribution.lezWatchLinkLabel(for: name))
        .accessibilityHint("Opens in Safari")
        .accessibilityIdentifier("lezwatch-source-link")
    }
}

/// TVmaze's credit, shown with any TVmaze schedule or episode data: a link to
/// TVmaze (the show's own TVmaze page when known) and to the CC BY-SA 4.0
/// license the data is under.
struct TVmazeCreditView: View {
    let credit: Attribution.TVmazeCredit

    @Environment(\.openURL) private var openURL
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        // Side by side, stacked at accessibility text sizes. One layout
        // whose axis changes, not `ViewThatFits`: that builds both
        // arrangements, and Xcode's accessibility audit reported the link in
        // it as "Dynamic Type font sizes are partially unsupported".
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 0))
            : AnyLayout(HStackLayout(spacing: 12))
        layout { links }
            .font(.footnote)
    }

    @ViewBuilder
    private var links: some View {
        Button(credit.source.title) { openURL(credit.source.url) }
            .frame(minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
            .accessibilityHint("Opens TVmaze in Safari")
            .accessibilityIdentifier("tvmaze-credit-link")
        Button(credit.license.title) { openURL(credit.license.url) }
            .frame(minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
            .accessibilityLabel("License: \(credit.license.title)")
            .accessibilityHint("Opens the license in Safari")
            .accessibilityIdentifier("tvmaze-license-link")
    }
}
