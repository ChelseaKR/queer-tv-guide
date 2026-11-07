import SwiftUI
import GuideCore

/// "Has anyone died so far?" (DECISIONS 0043), under the show's own reveal.
/// The viewer says where they are; the deaths up to there are behind one
/// tap, and the deaths after it behind a second tap that only appears once
/// the first is open. Changing the place closes both again.
///
/// Before any tap, nothing here depends on whether the show has a death:
/// the picker's ranges come from LezWatch.TV's season count (already on the
/// screen), never from the episode list, which exists only for shows with a
/// death (`SoFar.seasonRange`). The answers are not built while closed, so
/// VoiceOver cannot read them (`SpoilerReveal`).
///
/// Where the viewer is stays on this device (`WatchPositionStore`).
struct SoFarSection: View {
    let show: Show
    let cast: [Character]

    /// Mirrors of the UI-test identifiers (AccessibilityAuditTests).
    static let soFarIdentifier = "so-far-answer"
    static let laterIdentifier = "later-deaths-answer"

    private static let store = WatchPositionStore()

    @State private var position: SoFar.Position
    @State private var soFarOpen = false
    @State private var laterOpen = false
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    init(show: Show, cast: [Character]) {
        self.show = show
        self.cast = cast
        _position = State(initialValue: SoFar.clamped(Self.store.position(for: show.id) ?? .start, for: show))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Has anyone died so far?")
                .font(.headline)
                .accessibilityAddTraits(.isHeader)
            Text("Where are you?")
                .font(.subheadline.weight(.semibold))
                .accessibilityAddTraits(.isHeader)
            picker(
                "Season", value: seasonBinding, in: SoFar.seasonRange(for: show),
                identifier: "so-far-season"
            )
            picker(
                "Episode", value: episodeBinding, in: SoFar.episodeRange,
                identifier: "so-far-episode"
            )
            Text("Kept on this device only.")
                .font(.caption)
                .foregroundStyle(.subdued)
            SpoilerReveal(
                prompt: "Reveal deaths so far",
                revealedHint: "Reveals recorded deaths in \(show.title) up to \(position.spoken).",
                identifier: Self.soFarIdentifier,
                isRevealed: $soFarOpen
            ) {
                soFarAnswer
            }
            if soFarOpen {
                SpoilerReveal(
                    prompt: "Reveal later deaths",
                    revealedHint: "Reveals recorded deaths after \(position.spoken). This may spoil what's ahead.",
                    identifier: Self.laterIdentifier,
                    isRevealed: $laterOpen
                ) {
                    laterAnswer
                }
            }
        }
        .onChange(of: position) { _, new in
            Self.store.set(new, for: show.id)
            // A new place closes both answers: what was open was for the old one.
            soFarOpen = false
            laterOpen = false
        }
    }

    private var seasonBinding: Binding<Int> {
        Binding(get: { position.season }, set: { position = SoFar.Position(season: $0, episode: position.episode) })
    }

    private var episodeBinding: Binding<Int> {
        Binding(get: { position.episode }, set: { position = SoFar.Position(season: position.season, episode: $0) })
    }

    /// "Season 3" with a stepper: side by side, or stacked at the
    /// accessibility text sizes so the label is never clipped. VoiceOver
    /// hears one adjustable element, "Season, 3".
    private func picker(_ name: String, value: Binding<Int>, in range: ClosedRange<Int>, identifier: String) -> some View {
        let layout = dynamicTypeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4))
            : AnyLayout(HStackLayout(spacing: 12))
        return layout {
            Text("\(name) \(value.wrappedValue)")
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityHidden(true)
            Stepper(name, value: value, in: range)
                .labelsHidden()
                .accessibilityValue("\(value.wrappedValue)")
                .accessibilityIdentifier(identifier)
        }
    }

    private var answer: SoFar.Answer {
        SoFar.answer(show: show, cast: cast, at: position)
    }

    private var soFarAnswer: some View {
        let a = answer
        return VStack(alignment: .leading, spacing: 6) {
            Text(a.headline)
            lines(a.soFar)
            lines(a.uncertain)
            ForEach(Array(a.notes.enumerated()), id: \.offset) { _, note in
                Text(note)
                    .font(.callout)
                    .foregroundStyle(.subdued)
            }
            Text(a.footer)
                .font(.caption)
                .foregroundStyle(.subdued)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a.spoken + " " + a.footer)
    }

    private var laterAnswer: some View {
        let a = answer
        return VStack(alignment: .leading, spacing: 6) {
            Text(a.laterHeadline)
            lines(a.later)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a.laterSpoken)
    }

    private func lines(_ texts: [String]) -> some View {
        ForEach(Array(texts.enumerated()), id: \.offset) { _, text in
            Text(text)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
