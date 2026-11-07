import SwiftUI
import UIKit

/// Colors chosen for contrast, because Xcode's accessibility audit
/// (AccessibilityAuditTests) flagged the system defaults on this app's
/// backgrounds: `.secondary` text is ~3.4:1 on white and the default blue
/// accent ~4.0:1, both under WCAG AA's 4.5:1 for body-size text.
///
/// The accent is queerframe.app's aubergine pair (DECISIONS 0040), and coral
/// is only ever an edge, never text. `tests/test_app_accent_contrast.py`
/// reads these hex values and holds every text use to 4.5:1 in both schemes.
extension ShapeStyle where Self == Color {
    /// The app-wide tint (links, buttons, navigation rows, the selected tab):
    /// aubergine #6A2C9C in light mode (8.6:1 on white, 7.7:1 on the grouped
    /// gray) and lilac #D9B8FF in dark mode (12.3:1 on black, 8.1:1 on the
    /// #2C2C2E cell).
    static var accessibleAccent: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(rgb: 0xD9B8FF)
                : UIColor(rgb: 0x6A2C9C)
        })
    }

    /// Text on an accent fill (`.borderedProminent`): white on aubergine
    /// (8.6:1); in dark mode the lilac fill is too light for white (1.7:1),
    /// so the label is the site's dark aubergine #1D1027 (10.6:1).
    static var onAccent: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(rgb: 0x1D1027)
                : UIColor(rgb: 0xFFFFFF)
        })
    }

    /// Coral, for an edge only (the Reveal control's outline), never for
    /// text: it is under 3:1 on white.
    static var accentEdge: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(rgb: 0xFF8A6B)
                : UIColor(rgb: 0xFF6F4F)
        })
    }

    /// De-emphasized text that still clears 4.5:1 with margin: ~10:1 on
    /// white and ~9:1 on the grouped-list gray in light mode, ~10:1 on black
    /// in dark mode.
    static var subdued: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(white: 0.78, alpha: 1)
                : UIColor(white: 0.25, alpha: 1)
        })
    }
}

extension UIColor {
    /// A color from a 0xRRGGBB literal, so the palette reads as the hex the
    /// website and the Android theme use.
    convenience init(rgb: UInt32) {
        self.init(
            red: CGFloat((rgb >> 16) & 0xFF) / 255,
            green: CGFloat((rgb >> 8) & 0xFF) / 255,
            blue: CGFloat(rgb & 0xFF) / 255,
            alpha: 1
        )
    }
}

/// A list section header in `.subdued`. The system's grouped-list header gray
/// measured 3.3:1 on the grouped background (#85858B on #F2F2F7, iOS 26.5),
/// which the audit reports as "Contrast nearly passed": it clears only the
/// large-text threshold.
struct SubduedSectionHeader: View {
    let title: String

    var body: some View {
        Text(title)
            .foregroundStyle(.subdued)
            .accessibilityAddTraits(.isHeader)
    }
}

extension Section where Parent == SubduedSectionHeader, Footer == EmptyView, Content: View {
    /// `Section("Title") { … }` with a header that clears 4.5:1.
    init(subdued title: String, @ViewBuilder content: () -> Content) {
        self.init(content: content, header: { SubduedSectionHeader(title: title) })
    }
}

/// `LabeledContent` draws its value ("3 of 5", "Yes", a coverage count) in
/// the system `.secondary` gray, measured at 3.4:1 on white (#8A8A8E). The
/// audit does not report it, perhaps because those rows are read as one
/// combined element, but it is under 4.5:1 for anyone reading the screen.
/// This style keeps the system layout (label leading, value trailing) with
/// the value in `.subdued`, and stacks the two at accessibility text sizes
/// so neither is squeezed.
struct SubduedValueLabeledContentStyle: LabeledContentStyle {
    func makeBody(configuration: Configuration) -> some View {
        SubduedValueRow(configuration: configuration)
    }
}

private struct SubduedValueRow: View {
    let configuration: LabeledContentStyleConfiguration

    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        Group {
            if dynamicTypeSize.isAccessibilitySize {
                VStack(alignment: .leading, spacing: 2) {
                    configuration.label
                    configuration.content
                        .foregroundStyle(.subdued)
                }
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    configuration.label
                    Spacer(minLength: 8)
                    configuration.content
                        .foregroundStyle(.subdued)
                        .multilineTextAlignment(.trailing)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

extension View {
    /// iOS 26 fades scrolling content into a soft blur as it nears the
    /// floating tab bar, so text scrolling into that band is drawn lighter
    /// than its color. With the soft edge, the audit reported 4 contrast
    /// failures at the bottom of Search. With this change and nothing else
    /// on that screen, it reported none. The hard edge keeps content at
    /// full contrast up to the bar and puts an opaque backing behind the bar
    /// itself. Earlier iOS versions have no edge effect, so nothing changes
    /// there.
    @ViewBuilder
    func legibleScrollEdges() -> some View {
        if #available(iOS 26.0, *) {
            scrollEdgeEffectStyle(.hard, for: .bottom)
        } else {
            self
        }
    }
}

extension View {
    /// With Reduce Motion on, SwiftUI animations in this subtree are
    /// dropped: disclosure groups, list changes and reveals change at once
    /// instead of sliding or fading. System transitions (navigation pushes,
    /// sheets) follow the setting on their own.
    func reduceMotionRespected() -> some View {
        modifier(ReduceMotionRespected())
    }
}

private struct ReduceMotionRespected: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content.transaction { transaction in
            if reduceMotion { transaction.animation = nil }
        }
    }
}

/// An empty or error state built from Dynamic Type text styles, in place of
/// `ContentUnavailableView`, whose description text the audit reported as
/// not scaling and clipping at large sizes.
struct EmptyState: View {
    let title: String
    let systemImage: String
    var message: String? = nil

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: systemImage)
                .font(.largeTitle)
                .foregroundStyle(.subdued)
                .accessibilityHidden(true)
            Text(title)
                .font(.title2.bold())
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            if let message {
                Text(message)
                    .font(.body)
                    .foregroundStyle(.subdued)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
    }
}
