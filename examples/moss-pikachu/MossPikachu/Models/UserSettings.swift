import Foundation

nonisolated struct UserSettings: Codable, Equatable, Sendable {
    /// Hybrid search blend: 0.0 keyword-heavy, 1.0 semantic-only. Default balanced at 0.75.
    var searchAlpha: Double = 0.75

    var indexDocuments: Bool = true
    var indexDesktop: Bool = true
    var indexDownloads: Bool = true
    var indexMovies: Bool = false
    var indexMusic: Bool = false
    var indexPictures: Bool = false
    var indexPublic: Bool = false
    var indexICloudDrive: Bool = false

    nonisolated private static let storageKey = "picklight.userSettings"
    nonisolated private static let legacyStorageKey = "moss.pikachu.userSettings"

    nonisolated static func load() -> UserSettings {
        if let data = UserDefaults.standard.data(forKey: storageKey),
           let settings = try? JSONDecoder().decode(UserSettings.self, from: data) {
            return settings
        }
        if let data = UserDefaults.standard.data(forKey: legacyStorageKey),
           let settings = try? JSONDecoder().decode(UserSettings.self, from: data) {
            return settings
        }
        return UserSettings()
    }

    nonisolated func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }
}
