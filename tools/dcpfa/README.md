# DCPFA Tools

This folder contains helper scripts, validators, test sources, and experiment
metadata for the DCPFA MVP work. Most files here are executable scripts, but not
all of them are meant to be run directly.

## Quick Reference

| File | Executable | Purpose |
| --- | --- | --- |
| `run_mvp_trials.py` | Yes | Runs the official CPFA vs DCPFA trial matrix, writes raw results, writes summary statistics, and generates the boxplot PNG. |
| `official_experiments.csv` | No | Manifest consumed by `run_mvp_trials.py`; lists the official XMLs and trial counts. |
| `validate_official_xmls.py` | Yes | Checks that the six official MVP experiment XMLs match the required arena, robot count, resource count, runtime, and communication settings. |
| `validate_communication.py` | Yes | Checks communication logs and source invariants for the decentralized pheromone-sharing implementation. |
| `test_pheromone_memory.sh` | Yes | Builds and runs the standalone pheromone memory smoke test. |
| `pheromone_memory_smoke_test.cpp` | No | C++ source for the smoke test used by `test_pheromone_memory.sh`. |
| `run_dcpfa_visualization.sh` | Yes | Runs the short DCPFA visualization experiment, optionally headless. |
| `dcpfs_visualization.sh` | Yes | Compatibility wrapper that forwards to `run_dcpfa_visualization.sh`. |

## Main Trial Runner

Use this to run the official experiment set:

```bash
python3 tools/dcpfa/run_mvp_trials.py --workers 4 --resume
```

This command builds the project first, then runs every row in
`official_experiments.csv`. The default manifest currently defines 300 total
runs: 50 trials for CPFA and 50 trials for DCPFA across Random, Powerlaw, and
Clustered distributions.

Outputs are written to:

```text
results/dcpfa_mvp/raw_results.csv
results/dcpfa_mvp/improvement_summary.csv
results/dcpfa_mvp/boxplot_by_distribution.png
```

Useful options:

```bash
# Skip the build if the project is already compiled.
python3 tools/dcpfa/run_mvp_trials.py --workers 4 --resume --skip-build

# Run one trial per manifest row as a quick smoke test.
python3 tools/dcpfa/run_mvp_trials.py --trials 1 --workers 2 --skip-build --results-dir results/dcpfa_mvp/quick_check

# Resume after an interrupted run.
python3 tools/dcpfa/run_mvp_trials.py --workers 4 --resume --skip-build
```

`--resume` skips completed successful rows in `raw_results.csv`, so it is safe
to use for long runs.

## Experiment Manifest

`official_experiments.csv` is data rather than a script. It tells the runner:

- which algorithm is being tested
- which food distribution is used
- which experiment XML to run
- how many trials to run

Edit this file when changing the official experiment matrix.

## Validators

Run this after editing official XMLs or the manifest:

```bash
python3 tools/dcpfa/validate_official_xmls.py
```

It verifies the expected six official XMLs:

- CPFA Random, Powerlaw, Clustered
- DCPFA Random, Powerlaw, Clustered

It also checks that each uses the expected 10 x 10 m arena, 24 robots, 256 food
items, 720-second runtime, and 50-trial manifest entry.

Run this after a DCPFA communication smoke run:

```bash
python3 tools/dcpfa/validate_communication.py
```

It checks the communication log and source-level invariants, including:

- accepted pheromone transfers stay within the configured radius
- direct and relay communication events are present
- receiver cache growth is observed
- local memory is used instead of global pheromone sharing
- target priority remains site fidelity, then local pheromone, then random

By default it reads:

```text
results/dcpfa_mvp/logs/communication_events.csv
```

## Pheromone Memory Smoke Test

Run:

```bash
bash tools/dcpfa/test_pheromone_memory.sh
```

The shell script compiles `pheromone_memory_smoke_test.cpp` into:

```text
build/tools/dcpfa/pheromone_memory_smoke_test
```

Then it runs that binary. The smoke test verifies local pheromone creation,
deterministic IDs, duplicate merging, relay export, target selection, decay, and
pruning.

## Visualization Helpers

Run the short DCPFA visualization experiment:

```bash
bash tools/dcpfa/run_dcpfa_visualization.sh
```

Run it headless:

```bash
bash tools/dcpfa/run_dcpfa_visualization.sh --headless
```

Skip build checks when already compiled:

```bash
bash tools/dcpfa/run_dcpfa_visualization.sh --headless --no-build
```

Use a different XML:

```bash
bash tools/dcpfa/run_dcpfa_visualization.sh --xml experiments/dcpfa_mvp/DCPFA_Random_24r_256tags_10x10.xml
```

`dcpfs_visualization.sh` is just a forwarding wrapper kept for compatibility.

## Typical Workflow

After changing DCPFA communication or pheromone memory code:

```bash
bash tools/dcpfa/test_pheromone_memory.sh
bash tools/dcpfa/run_dcpfa_visualization.sh --headless --no-build
python3 tools/dcpfa/validate_communication.py
```

After changing official XMLs or the manifest:

```bash
python3 tools/dcpfa/validate_official_xmls.py
```

For the full CPFA vs DCPFA comparison:

```bash
python3 tools/dcpfa/run_mvp_trials.py --workers 4 --resume
```
