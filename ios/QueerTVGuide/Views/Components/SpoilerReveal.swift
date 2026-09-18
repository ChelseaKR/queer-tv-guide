import SwiftUI

/// A tap-to-reveal control for spoiler content ("does she die"). Hidden by
/// default; the user chooses to see it. Respects Reduce Motion by skipping
/// the reveal animation, and is fully labelled for VoiceOver in both states
/// so a screen reader user gets the same choice a sighted user does.
struct SpoilerReveal<Content: View>: View {
    let prompt: String
    let revealedHint: String
    @ViewBuilder let content: () -> Content

    @State private var revealed = false
    @AccessibilityFocusState private var answerFocused: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            if revealed {
                // The button a VoiceOver user just activated disappears;
                // move focus to the answer that replaced it so it is read
                // out, rather than leaving focus to land somewhere else.
                content()
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
                .accessibilityHint(revealedHint)
            }
        }
        .animation(reduceMotion ? nil : .default, value: revealed)
    }
}
