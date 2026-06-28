// swift-tools-version: 5.9
//
// Moss iOS SDK — Swift Package Manager manifest.
//
// The `Moss` library wraps the precompiled `MossC` xcframework hosted as a
// GitHub Release asset on this repo. Xcode downloads the binary on first
// resolve, verifies the SHA-256 checksum below, and links it into the
// consuming target.
//
// To consume from another package or app:
//
//     dependencies: [
//         .package(url: "https://github.com/usemoss/moss", from: "0.4.0"),
//     ],
//     targets: [
//         .target(name: "YourTarget", dependencies: [
//             .product(name: "Moss", package: "moss"),
//         ]),
//     ]
//
// Or, in Xcode: File ▸ Add Package Dependencies ▸ https://github.com/usemoss/moss
//
// The Swift wrapper sources live under `sdks/swift/Sources/Moss/`. The
// xcframework binary is not committed to this repo — it ships as a release
// asset. Bump both the URL tag segment and the checksum together on every
// new tag.
import PackageDescription

let package = Package(
    name: "Moss",
    platforms: [.iOS(.v15)],
    products: [
        .library(name: "Moss", targets: ["Moss"]),
    ],
    targets: [
        .binaryTarget(
            name: "MossC",
            url: "https://github.com/usemoss/moss/releases/download/v0.5.0/Moss.xcframework.zip",
            checksum: "f1df7a8897c9ff04090536b95471299faa0cffde741e2ff9d6e1974ff62467d2"
        ),
        .target(
            name: "Moss",
            dependencies: ["MossC"],
            path: "sdks/swift/Sources/Moss"
        ),
    ]
)
