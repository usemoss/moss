// swift-tools-version: 5.9
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
            url: "https://github.com/usemoss/moss/releases/download/v0.15.0/Moss.xcframework.zip",
            checksum: "17c98a935dae8eb1ca3953599d8b6e1654abb2076b4e2a90bbd869cdcda4dcc7"
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
