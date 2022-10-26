#!/bin/bash

pushd /chromium/src
  ninja -C out/Release third_party/devtools-frontend/src/test:test

  pushd third_party/devtools-frontend/src
    mkdir -p out/Release/gen
    cp -r ../../../out/Release/gen/third_party/devtools-frontend/src/* out/Release/gen
    cp -r scripts out/Release/gen/scripts

    ./third_party/node/node.py --output scripts/test/run_test_suite.js \
      '--test-suite-path=gen/test/e2e' \
      '--test-suite-source-dir=test/e2e' \
      '--test-server-type="hosted-mode"' \
      '--target=Release' \
      '--chrome-binary-path="/chromium/src/out/Release/chrome"' \
      'media/media-tab_test.ts'
  popd
popd
