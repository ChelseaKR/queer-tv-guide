import SwiftUI
import GuideCore
import UIKit

/// The Favorites screen's reminders switch, shown only while
/// `FeatureFlags.episodeReminders` is on. Turning it on first explains what
/// a reminder is and is not (`ReminderPrimingView`); only "Turn on
/// reminders" there asks the system for permission.
struct RemindersSection: View {
    /// Owned by FavouritesView, which presents the explanation sheet: a
    /// sheet attached inside a List row was dismissed as soon as the list
    /// redrew (measured in RemindersUITests).
    @Binding var showingPrimer: Bool

    @Environment(\.openURL) private var openURL
    /// The user's choice, read live, so the switch turns on when
    /// `ReminderScheduler.enable` stores a granted permission.
    @AppStorage(ReminderScheduler.enabledKey) private var storedOn = false
    @State private var deniedInSettings = false

    var body: some View {
        Section {
            Toggle("New-episode reminders", isOn: Binding(
                get: { FeatureFlags.episodeReminders && storedOn },
                set: { wantsOn in
                    if wantsOn {
                        showingPrimer = true
                    } else {
                        Task { await ReminderScheduler.disable() }
                    }
                }
            ))
            .accessibilityHint("Reminds you on the day a favorite show has a new episode listed. Set on this iPhone only.")
            .task(id: storedOn) {
                deniedInSettings = storedOn ? false : await ReminderScheduler.isDeniedInSettings()
            }
            if deniedInSettings {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Notifications are off for this app in Settings, so no reminder can appear.")
                        .foregroundStyle(.subdued)
                    Button("Open Settings") {
                        if let url = URL(string: UIApplication.openNotificationSettingsURLString) { openURL(url) }
                    }
                }
            }
        } footer: {
            Text("Reminders are set on this iPhone and follow the data file, so a schedule changed since the last refresh can make one wrong.")
                .foregroundStyle(.subdued)
        }
    }
}

/// Before the system's permission prompt: what a reminder says, where it
/// comes from, and what it never carries.
struct ReminderPrimingView: View {
    let finish: (_ accepted: Bool) -> Void

    static let points: [(image: String, text: String)] = [
        ("calendar.badge.clock", "On the day a favorite show has a new episode listed, you get one reminder: the show's name and the episode number."),
        ("eye.slash", "Episode titles are left out, and nothing about any character, so a reminder cannot spoil anything on your lock screen."),
        ("iphone", "This iPhone sets the reminders itself. Nothing is sent to a server, and nothing about you leaves this phone."),
        ("arrow.clockwise", "Reminders follow the data file. If a schedule changes after your last refresh, one can be early, late or wrong."),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Text("New-episode reminders")
                        .font(.largeTitle.bold())
                        .accessibilityAddTraits(.isHeader)
                    ForEach(Self.points, id: \.text) { point in
                        HStack(alignment: .firstTextBaseline, spacing: 14) {
                            Image(systemName: point.image)
                                .font(.title2)
                                .foregroundStyle(.accessibleAccent)
                                .frame(minWidth: 32)
                                .accessibilityHidden(true)
                            Text(point.text)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    Text("iOS asks next whether to allow notifications. You can change your mind in Settings at any time.")
                        .foregroundStyle(.subdued)
                    Button {
                        finish(true)
                    } label: {
                        Text("Turn on reminders").font(.headline).frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .accessibilityIdentifier("reminders-accept")
                    Button {
                        finish(false)
                    } label: {
                        Text("Not now").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.large)
                    .accessibilityIdentifier("reminders-decline")
                }
                .padding()
            }
        }
    }
}
