require 'json'

package = JSON.parse(File.read(File.join(__dir__, '..', 'package.json')))

Pod::Spec.new do |s|
  s.name           = 'MossReactNative'
  s.version        = package['version']
  s.summary        = package['description']
  s.description    = package['description']
  s.license        = package['license']
  s.author         = package['author']
  s.homepage       = package['homepage']
  s.platforms      = { :ios => '16.4' }
  s.swift_version  = '5.9'
  s.source         = { git: 'https://github.com/usemoss/moss.git' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  # System frameworks used by libmoss (see examples/c + Swift SDK)
  s.frameworks = 'Security', 'SystemConfiguration', 'UIKit'

  s.prepare_command = <<-CMD
    bash "#{__dir__}/scripts/download-moss-xcframework.sh"
  CMD

  s.vendored_frameworks = 'Frameworks/Moss.xcframework'
  s.preserve_paths = [
    'Frameworks/Moss.xcframework',
    'scripts',
  ]

  # Keep Frameworks/ out of the source glob (Expo third-party library guidance)
  s.source_files = '*.{h,m,mm,swift}'

  xc_headers = '"${PODS_XCFRAMEWORKS_BUILD_DIR}/MossReactNative/Headers"'
  xc_libdir  = '"${PODS_XCFRAMEWORKS_BUILD_DIR}/MossReactNative"'

  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'OTHER_SWIFT_FLAGS' => '$(inherited) -D EXPO_CONFIGURATION_$(CONFIGURATION:upper)',
    # Make `import MossC` resolve the Headers/module.modulemap from the xcframework
    'HEADER_SEARCH_PATHS' => "$(inherited) #{xc_headers}",
    'SWIFT_INCLUDE_PATHS' => "$(inherited) #{xc_headers}",
    'LIBRARY_SEARCH_PATHS' => "$(inherited) #{xc_libdir}",
    # Simulator binary is arm64-only (Apple Silicon)
    'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'x86_64',
  }

  s.user_target_xcconfig = {
    'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'x86_64',
  }
end
