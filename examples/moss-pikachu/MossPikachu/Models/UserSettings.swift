import Foundation

nonisolated struct UserSettings: Codable, Equatable, Sendable {
    var indexDocuments: Bool = true
    var indexDesktop: Bool = true
    var indexDownloads: Bool = true
    var indexICloudDrive: Bool = false
    var launchAtLogin: Bool = false
    var mossCloudSync: Bool = false

    nonisolated private static let storageKey = "moss.pikachu.userSettings"

    nonisolated static func load() -> UserSettings {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let settings = try? JSONDecoder().decode(UserSettings.self, from: data) else {
            return UserSettings()
        }
        return settings
    }

    nonisolated func save() {
        if let data = try? JSONEncoder().encode(self) {
            UserDefaults.standard.set(data, forKey: Self.storageKey)
        }
    }
}
