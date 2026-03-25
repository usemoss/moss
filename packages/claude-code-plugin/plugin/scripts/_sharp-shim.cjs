
module.exports = function sharp() { throw new Error('sharp not available in bundled plugin'); };
module.exports.cache = () => {};
module.exports.concurrency = () => {};
module.exports.counters = () => ({});
module.exports.simd = () => false;
module.exports.versions = {};
