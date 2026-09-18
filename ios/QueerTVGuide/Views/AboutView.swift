import SwiftUI
import GuideCore

struct AboutView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openURL) private var openURL

    var body: some View {
        NavigationStack {
            List {
                Section("Privacy") {
                    Text("No account, no analytics, no crash reporting, no third-party SDKs. Nothing leaves this device except one request for the data file this app reads — a plain, cookieless GET of a static file, sent only when you open the app or pull to refresh.")
                        .accessibilityLabel("Privacy posture: no account, no analytics, no crash reporting, no third-party SDKs. Nothing leaves this device except one request for the data file this app reads.")
                    Text("Favourites are stored only on this device and are never sent anywhere.")
                    Button("Privacy policy") { openURL(PrivacyPolicy.url) }
                        .accessibilityHint("Opens in Safari")
                }

                if let snapshot = model.snapshot {
                    Section("Data sources") {
                        ForEach(snapshot.attribution) { item in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.name).font(.headline)
                                    // "LezWatch.TV" is read "LezWatch dot T V"
                                    // otherwise (and the audit flags it).
                                    .accessibilityLabel(item.name.replacingOccurrences(of: ".", with: " "))
                                Text(item.text)
                                Text("Licence: \(item.licenceName)")
                                    .font(.caption)
                                    .foregroundStyle(.subdued)
                                Button(item.url.absoluteString) { openURL(item.url) }
                                    .font(.caption)
                                    // A caption-sized link is under the 44 pt
                                    // minimum hit area without this.
                                    .frame(minHeight: 44, alignment: .leading)
                                    .contentShape(Rectangle())
                                    .accessibilityLabel("Visit \(item.name.replacingOccurrences(of: ".", with: " "))")
                                    .accessibilityHint("Opens in Safari")
                            }
                            .padding(.vertical, 4)
                        }
                    }

                    Section("Licence") {
                        Text(snapshot.licence.notice)
                        Button(snapshot.licence.snapshot.name) { openURL(snapshot.licence.snapshot.url) }
                            .font(.caption)
                            .frame(minHeight: 44, alignment: .leading)
                            .contentShape(Rectangle())
                            .accessibilityHint("Opens in Safari")
                    }

                    Section("Coverage") {
                        LabeledContent("Shows", value: "\(snapshot.coverage.lezwatch.shows.fetched) of \(snapshot.coverage.lezwatch.shows.available.map(String.init) ?? "an unreported total")")
                        LabeledContent("Characters", value: "\(snapshot.coverage.lezwatch.characters.fetched) of \(snapshot.coverage.lezwatch.characters.available.map(String.init) ?? "an unreported total")")
                        LabeledContent("Schedules matched", value: "\(snapshot.coverage.tvmaze.joined) of \(snapshot.coverage.tvmaze.showsTotal)")
                    }

                    Section("This snapshot") {
                        DataStatusFooter(generatedAt: snapshot.generatedAt, refreshError: model.lastRefreshError)
                        if let origin = model.origin {
                            Text(origin == .bundled ? "Bundled with the app" : "Downloaded")
                                .font(.caption)
                                .foregroundStyle(.subdued)
                        }
                    }
                }

                Section("Version") {
                    LabeledContent("App", value: "\(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—") (\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "—"))")
                }
            }
            .navigationTitle("About \(AppIdentity.displayName)")
        }
    }
}
