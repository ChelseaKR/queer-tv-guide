import SwiftUI

/// A tap-to-reveal control for spoiler content ("does she die"). Hidden by
/// default; the user chooses to see it. Respects Reduce Motion by skipping
/// the reveal animation, and is fully labeled for VoiceOver in both states
/// so a screen reader user gets the same choice a sighted user does.
///
/// While closed, the answer is not built at all, so it is not in the
/// accessibility tree and VoiceOver cannot read it. Hiding it visually
/// instead (opacity, blur, a cover) would leave it readable by VoiceOver.
/// `AccessibilityAuditTests` checks this: before the tap, no element carries
/// the answer's text or `answerIdentifier`.
struct SpoilerReveal<Content: View>: View {
    /// Identifies the revealed answer to UI tests. Not spoken by VoiceOver.
    static var answerIdentifier: String { "spoiler-answer" }
    let prompt: String
    let revealedHint: String
    /// The answer's UI-test identifier; screens with more than one reveal
    /// give each its own (the "so far" reveals, DECISIONS 0043).
    var identifier: String = "spoiler-answer"
    /// Set when the screen needs to know, or reset, whether the answer is
    /// open (the "so far" reveals close again when the viewer's place
    /// changes). Otherwise the reveal keeps its own state.
    var isRevealed: Binding<Bool>? = nil
    @ViewBuilder let content: () -> Content

    @State private var ownRevealed = false
    private var revealed: Bool {
        get { isRevealed?.wrappedValue ?? ownRevealed }
        nonmutating set {
            if let isRevealed { isRevealed.wrappedValue = newValue } else { ownRevealed = newValue }
        }
    }
    @AccessibilityFocusState private var answerFocused: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            if revealed {
                // The button a VoiceOver user just activated disappears;
                // move focus to the answer that replaced it so it is read
                // out, rather than leaving focus to land somewhere else.
                content()
                    .accessibilityIdentifier(identifier)
                    .accessibilityFocused($answerFocused)
                    .onAppear { answerFocused = true }
                    .transition(reduceMotion ? .identity : .opacity)
            } else {
                Button {
                    withAnimation(reduceMotion ? nil : .default) {
                        revealed = true
                    }
                } label: {
                    Label(prompt, systemImage: "eye.slash")
                        .font(.body.weight(.medium))
                }
                .buttonStyle(.bordered)
                .buttonBorderShape(.capsule)
                // The one coral touch (DECISIONS 0040): an edge around the
                // sealed answer, as on queerframe.app. Decoration only.
                .overlay {
                    Capsule()
                        .strokeBorder(.accentEdge, lineWidth: 2)
                        .accessibilityHidden(true)
                        .allowsHitTesting(false)
                }
                .accessibilityHint(revealedHint)
            }
        }
        .animation(reduceMotion ? nil : .default, value: revealed)
        // A light tap as the answer opens. It fires only on the user's own
        // tap: `revealed` starts false and nothing else sets it.
        .sensoryFeedback(.impact(weight: .light), trigger: revealed)
    }
}
