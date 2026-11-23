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
            url: "https://github.com/usemoss/moss/releases/download/v0.17.0/Moss.xcframework.zip",
            checksum: "b9718f1b5bb6ad36125747c7a44ed04fc78af5fc2533500ab6296bf371cf1ef1"
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
