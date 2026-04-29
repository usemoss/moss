const { getDefaultConfig } = require('expo/metro-config')

const config = getDefaultConfig(__dirname)

// onnxruntime-web is the browser/WASM build — redirect every import of it
// (including those deep inside node_modules) to the React Native native build.
const originalResolveRequest = config.resolver.resolveRequest
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName === 'onnxruntime-web' || moduleName.startsWith('onnxruntime-web/')) {
    const rn = moduleName.replace('onnxruntime-web', 'onnxruntime-react-native')
    return (originalResolveRequest ?? context.resolveRequest)(context, rn, platform)
  }
  return (originalResolveRequest ?? context.resolveRequest)(context, moduleName, platform)
}

module.exports = config
