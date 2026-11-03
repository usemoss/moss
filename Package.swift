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
            url: "https://github.com/usemoss/moss/releases/download/v0.13.0/Moss.xcframework.zip",
            checksum: "413a2460097c23da3a86b54aaa96e1a3150136ee8849cb6ad88d51c60b3dfb29"
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
