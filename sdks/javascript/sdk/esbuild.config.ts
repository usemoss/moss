/// <reference path="./types/esbuild-plugin-obfuscator.d.ts" />
// esbuild.config.ts
import * as esbuild from "esbuild";
import { BuildOptions } from "esbuild";
import { ObfuscatorPlugin } from "esbuild-plugin-obfuscator";

/**
 * Build configurations for different output formats
 */
const buildConfigs: BuildOptions[] = [
    {
        format: "esm" as esbuild.Format,
        outfile: "dist/index.esm.js",
        entryPoints: ["src/index.ts"],
    },
];

/**
 * Run the build process for all configurations
 */
const build = async (): Promise<void> => {
    try {
        const buildPromises = buildConfigs.map((config) =>
            esbuild.build({
                outfile: config.outfile,
                format: config.format,
                entryPoints: config.entryPoints,
                bundle: true,
                platform: "node" as esbuild.Platform,
                minify: true,
                minifyWhitespace: true,
                minifyIdentifiers: true,
                minifySyntax: true,
                treeShaking: true,
                keepNames: false,
                external: [
                    "@moss-dev/moss-core",
                ],
                plugins: [
                    ObfuscatorPlugin({
                        shouldObfuscateOutput: true,
                    })
                ],
            })
        );

        await Promise.all(buildPromises);
        console.log("Build completed successfully!");
    } catch (error) {
        console.error("Build failed:", error);
        process.exit(1);
    }
};

// Export build function for use in npm scripts
export default build;

// Run the build if this file is executed directly
if (typeof process !== 'undefined' && process.argv[1] &&
    (process.argv[1].endsWith('esbuild.config.ts') || process.argv[1].endsWith('esbuild.config.js'))) {
    build();
}
