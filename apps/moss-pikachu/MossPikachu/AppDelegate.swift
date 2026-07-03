import AppKit
import SwiftUI

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var floatingPetController: FloatingPetWindowController?
    private var searchOverlayController: SearchOverlayController?
    private var settingsWindowController: SettingsWindowController?
    private let hotKeyManager = HotKeyManager()
    private let searchService = SearchService()
    private let petStateController = PetStateController()
    private let searchPresentation = SearchOverlayPresentation()

    var debugMode: Bool {
        ProcessInfo.processInfo.arguments.contains("--debug")
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if debugMode {
            AppLogger.shared.isDebugEnabled = true
            AppLogger.shared.log("Moss Pikachu starting in debug mode")
        }

        setupSearchOverlay()
        setupFloatingPet()
        setupHotKey()
        setupSettingsWindow()

        Task {
            do {
                try await searchService.initialize()
                AppLogger.shared.isDebugEnabled = true
                AppLogger.shared.log("SearchService initialized")
                if searchService.indexedFileCount > 0 {
                    NotificationManager.shared.showSuccess(
                        "Indexed \(searchService.indexedChunkCount) chunks from \(searchService.indexedFileCount) files"
                    )
                }
            } catch {
                AppLogger.shared.isDebugEnabled = true
                AppLogger.shared.log("SearchService init failed: \(error.localizedDescription)")
                NotificationManager.shared.showError(error.localizedDescription)
            }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        searchService.shutdown()
        hotKeyManager.unregister()
    }

    // MARK: - Setup

    private func setupFloatingPet() {
        floatingPetController = FloatingPetWindowController(petStateController: petStateController)
        floatingPetController?.onPetClicked = { [weak self] in
            self?.openSearch()
        }
        floatingPetController?.onShowSettings = { [weak self] in
            self?.showSettings()
        }
        floatingPetController?.onQuit = { [weak self] in
            self?.quitApp()
        }
        floatingPetController?.show()
    }

    private func setupSearchOverlay() {
        searchOverlayController = SearchOverlayController(
            searchService: searchService,
            presentation: searchPresentation,
            anchorProvider: { [weak self] in
                self?.floatingPetController?.screenFrame
            }
        )
        searchOverlayController?.onPetStateChanged = { [weak self] state in
            self?.petStateController.state = state
        }
    }

    private func setupHotKey() {
        hotKeyManager.onHotKeyPressed = { [weak self] in
            Task { @MainActor in
                self?.toggleSearch()
            }
        }
        hotKeyManager.register()
    }

    private func setupSettingsWindow() {
        settingsWindowController = SettingsWindowController(searchService: searchService)
    }

    // MARK: - Actions

    private func openSearch() {
        if searchOverlayController?.isSearchVisible == true {
            searchOverlayController?.focusSearchField()
        } else {
            searchOverlayController?.show()
        }
    }

    @objc private func showSettings() {
        settingsWindowController?.show()
    }

    @objc private func quitApp() {
        NSApplication.shared.terminate(nil)
    }

    private func toggleSearch() {
        searchOverlayController?.toggle()
    }
}
