import SwiftUI
import UIKit

/// Colours chosen for contrast, because Xcode's accessibility audit
/// (AccessibilityAuditTests) flagged the system defaults on this app's
/// backgrounds: `.secondary` text is ~3.4:1 on white and the default blue
/// accent ~4.0:1, both under WCAG AA's 4.5:1 for body-size text.
extension ShapeStyle where Self == Color {
    /// The app-wide tint (links, buttons, navigation rows): a darker blue in
    /// light mode (~7:1 on white) and a lighter one in dark mode (~9:1 on
    /// black).
    static var accessibleAccent: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(red: 0.45, green: 0.72, blue: 1.0, alpha: 1)
                : UIColor(red: 0.0, green: 0.34, blue: 0.70, alpha: 1)
        })
    }

    /// De-emphasised text that still clears 4.5:1 with margin: ~10:1 on
    /// white and ~9:1 on the grouped-list grey in light mode, ~10:1 on black
    /// in dark mode.
    static var subdued: Color {
        Color(uiColor: UIColor { traits in
            traits.userInterfaceStyle == .dark
                ? UIColor(white: 0.78, alpha: 1)
                : UIColor(white: 0.25, alpha: 1)
        })
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
