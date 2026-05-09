#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build/tools/dcpfa"
TEST_BIN="${BUILD_DIR}/pheromone_memory_smoke_test"

mkdir -p "$BUILD_DIR"

cd "$ROOT_DIR"

c++ -std=c++17 -I"$ROOT_DIR" -I"$ROOT_DIR/source" \
  tools/dcpfa/pheromone_memory_smoke_test.cpp \
  source/DCPFA/DecentralizedPheromone.cpp \
  source/DCPFA/RobotPheromoneMemory.cpp \
  -L/usr/local/lib/argos3 -Wl,-rpath,/usr/local/lib/argos3 \
  -largos3core_simulator \
  -o "$TEST_BIN"

"$TEST_BIN"
