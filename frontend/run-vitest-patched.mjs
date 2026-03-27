/**
 * Patched vitest runner that intercepts the rollup native module
 * to work around macOS code signing restrictions with Electron's Node.js
 */
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const require = createRequire(import.meta.url);
const __dirname = dirname(fileURLToPath(import.meta.url));

// Patch Module._load to intercept rollup native module
const Module = require('module');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
  if (request.includes('rollup-darwin-arm64') || request.includes('rollup.darwin-arm64')) {
    // Return a mock that satisfies rollup's native module interface
    return {
      parse: () => Buffer.alloc(0),
      parseAsync: async () => Buffer.alloc(0),
      xxhashBase64Url: (b) => Buffer.from(b).toString('base64url').slice(0, 22),
      xxhashBase36: (b) => Buffer.from(b).toString('hex').slice(0, 13),
      xxhashBase16: (b) => Buffer.from(b).toString('hex').slice(0, 16),
    };
  }
  return originalLoad.apply(this, arguments);
};

// Now run vitest
const vitestCliPath = join(__dirname, 'node_modules/vitest/dist/cli.js');
await import(vitestCliPath);
