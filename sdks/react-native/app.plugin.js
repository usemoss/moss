const {
  createRunOncePlugin,
  withPodfileProperties,
} = require('@expo/config-plugins');

const pkg = require('./package.json');

/**
 * Expo config plugin for `@moss-dev/moss-react-native`.
 *
 * Ensures iOS deployment target is high enough for Moss.xcframework and
 * documents that a development build / prebuild is required (Expo Go is not
 * supported because this module ships custom native code).
 *
 * @param {import('@expo/config-plugins').ConfigPlugin} config
 */
const withMoss = (config) => {
  config = withPodfileProperties(config, (cfg) => {
    cfg.modResults['ios.deploymentTarget'] =
      cfg.modResults['ios.deploymentTarget'] || '16.4';
    return cfg;
  });
  return config;
};

module.exports = createRunOncePlugin(withMoss, pkg.name, pkg.version);
