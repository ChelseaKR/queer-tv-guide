import SwiftUI
import GuideCore

struct AboutView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openURL) private var openURL
    @State private var showingIntroduction = false

    var body: some View {
        NavigationStack {
            List {
                Section(subdued: "Privacy") {
                    Text("\(AppIdentity.displayName) collects nothing: no account, no analytics, no crash reporting, no third-party SDKs. Nothing leaves this device except one request for the data file this app reads — a plain, cookieless GET of a static file, sent only when you open the app, when you pull to refresh, or when you return to the app \(Presentation.returnRefreshRule).")
                        .accessibilityLabel("Privacy posture: \(AppIdentity.displayName) collects nothing. No account, no analytics, no crash reporting, no third-party SDKs. Nothing leaves this device except one request for the data file this app reads.")
                    // DECISIONS 0007: say plainly who serves that file and
                    // what a web server sees.
                    Text("That file is served by GitHub Pages, which, like any web server, sees your IP address and logs it for security. The developer never sees that log.")
                    Text("Favorites are stored only on this device and are never sent anywhere.")
                    Button("Privacy policy") { openURL(PrivacyPolicy.url) }
                        .accessibilityHint("Opens in Safari")
                    Button("Support") { openURL(SupportPage.url) }
                        .accessibilityHint("Opens in Safari")
                }

                if let snapshot = model.snapshot {
                    Section(subdued: "Data sources") {
                        ForEach(snapshot.attribution) { item in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.name).font(.headline)
                                    // "LezWatch.TV" is read "LezWatch dot T V"
                                    // otherwise (and the audit flags it).
                                    .accessibilityLabel(item.name.replacingOccurrences(of: ".", with: " "))
                                Text(item.text)
                                Button("License: \(item.licenseName)") { openURL(item.licenseURL) }
                                    .font(.caption)
                                    .frame(minHeight: 44, alignment: .leading)
                                    .contentShape(Rectangle())
                                    .accessibilityHint("Opens in Safari")
                                    .accessibilityIdentifier("license-link-\(item.source)")
                                Button(item.url.absoluteString) { openURL(item.url) }
                                    .font(.caption)
                                    // A caption-sized link is under the 44 pt
                                    // minimum hit area without this.
                                    .frame(minHeight: 44, alignment: .leading)
                                    .contentShape(Rectangle())
                                    .accessibilityLabel("Visit \(item.name.replacingOccurrences(of: ".", with: " "))")
                                    .accessibilityHint("Opens in Safari")
                                    .accessibilityIdentifier("source-link-\(item.source)")
                            }
                            .padding(.vertical, 4)
                        }
                        // Stated by the app itself, whatever the data says.
                        Text(Attribution.nonEndorsement)
                    }

                    Section(subdued: "License") {
                        Text(snapshot.license.notice)
                        Button(snapshot.license.snapshot.name) { openURL(snapshot.license.snapshot.url) }
                            .font(.caption)
                            .frame(minHeight: 44, alignment: .leading)
                            .contentShape(Rectangle())
                            .accessibilityHint("Opens in Safari")
                    }

                    Section(subdued: "Coverage") {
                        LabeledContent("Shows", value: "\(snapshot.coverage.lezwatch.shows.fetched) of \(snapshot.coverage.lezwatch.shows.available.map(String.init) ?? "an unreported total")")
                        LabeledContent("Characters", value: "\(snapshot.coverage.lezwatch.characters.fetched) of \(snapshot.coverage.lezwatch.characters.available.map(String.init) ?? "an unreported total")")
                        LabeledContent("Schedules matched", value: "\(snapshot.coverage.tvmaze.joined) of \(snapshot.coverage.tvmaze.showsTotal)")
                    }

                    Section(subdued: "This snapshot") {
                        DataStatusFooter(snapshot: snapshot)
                        if let origin = model.origin {
                            Text(origin == .bundled ? "Bundled with the app" : "Downloaded")
                                .font(.caption)
                                .foregroundStyle(.subdued)
                        }
                    }
                }

                Section(subdued: "Version") {
                    LabeledContent("App", value: "\(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—") (\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"))")
                }

                // The first-run page again, last, so the sections above keep
                // their place.
                Section {
                    Button("How \(AppIdentity.displayName) works") { showingIntroduction = true }
                        .accessibilityHint("Spoilers, sources and privacy, in one page")
                }
            }
            // Pull to check for a newer data file (the one GET).
            .refreshable { await model.refresh() }
            .navigationTitle("About \(AppIdentity.displayName)")
            .sheet(isPresented: $showingIntroduction) {
                OnboardingView(finish: { showingIntroduction = false }, isFirstRun: false)
            }
        }
    }
}
