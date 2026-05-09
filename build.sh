#!/usr/bin/env bash
set -euo pipefail

BUILD_EVOLVER="${BUILD_EVOLVER:-NO}"
BUILD_TYPE="${BUILD_TYPE:-Release}"

echo "Deleting and recreating the build directory "
rm -rf build
mkdir build

#export PKG_CONFIG_PATH=/opt/local/argos3/2.8.12.2/gcc/5.4.0/lib/pkgconfig
echo "Configuring Makefiles with CMAKE..."
cmake -S . -B build \
  -DBUILD_EVOLVER="${BUILD_EVOLVER}" \
  -DCMAKE_BUILD_TYPE="${BUILD_TYPE}"

echo "Making..."
cmake --build build

echo "Finished."
