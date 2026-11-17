// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Moss",
    platforms: [.iOS(.v15)],
    products: [
        .library(name: "Moss", targets: ["Moss"]),
    ],
    targets: [
        // MossC is not under this repository's BSD 2-Clause License.
        // Its terms are the PolyForm Shield License 1.0.0, in LICENSE.txt in the zip.
        .binaryTarget(
            name: "MossC",
            url: "https://github.com/usemoss/moss/releases/download/v0.16.0/Moss.xcframework.zip",
            checksum: "054bad915dea8f219bde016f36f69a9559277975e316da7b45403a780918c2ab"
        ),
        .target(
            name: "MossRuntimeBridge",
            dependencies: ["MossC"],
            path: "sdks/swift/Sources/MossRuntimeBridge",
            publicHeadersPath: "include"
        ),
        .target(
            name: "Moss",
            dependencies: ["MossC", "MossRuntimeBridge"],
            path: "sdks/swift/Sources/Moss"
        ),
    ]
)
