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
/// licence the data is under.
struct TVmazeCreditView: View {
    let credit: Attribution.TVmazeCredit

    @Environment(\.openURL) private var openURL

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) { links }
            VStack(alignment: .leading, spacing: 0) { links }
        }
        .font(.footnote)
    }

    @ViewBuilder
    private var links: some View {
        Button(credit.source.title) { openURL(credit.source.url) }
            .frame(minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
            .accessibilityHint("Opens TVmaze in Safari")
            .accessibilityIdentifier("tvmaze-credit-link")
        Button(credit.licence.title) { openURL(credit.licence.url) }
            .frame(minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
            .accessibilityLabel("Licence: \(credit.licence.title)")
            .accessibilityHint("Opens the licence in Safari")
            .accessibilityIdentifier("tvmaze-licence-link")
    }
}
