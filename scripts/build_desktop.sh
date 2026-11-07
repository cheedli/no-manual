#!/usr/bin/env bash
# Reproducible bundle of the Desktop half: desktop/src/plugin.src.js + three.js -> desktop/plugin.js
# Only @hermes/plugin-sdk, react and react/jsx-runtime stay external (the Desktop loader's allowlist).
# Not minified, so reviewers and the catalog scanner can read it.
set -euo pipefail
cd "$(dirname "$0")/../desktop"
npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund
npx esbuild src/plugin.src.js --bundle --format=esm --platform=browser --target=es2022 \
  --external:@hermes/plugin-sdk --external:react --external:react/jsx-runtime \
  --legal-comments=inline --outfile=plugin.js
ls -l plugin.js
rm -rf node_modules  # keep the plugin folder scanner-clean (validate scans the whole dir)
