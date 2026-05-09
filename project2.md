## MVP understanding

The project’s MVP is **not** to rewrite CPFA. It is to add a **decentralized pheromone-waypoint communication layer** on top of CPFA so robots can exchange pheromone waypoints with nearby robots instead of waiting to return to the central collection zone. The PDF says the current CPFA shares pheromone waypoints through a central server at the collection zone, and the goal is for robots to share directly with nearby robots within a **2-meter radius**; received pheromones should also be re-shared, and decayed pheromones below threshold should be deleted from every robot that has them. The required evaluation is 24 robots, 256 resources, 10 × 10 m arena, 12 minutes, 50 runs each for Random, Powerlaw, and Clustered distributions, with box plots and percentage improvement over original CPFA.  

In the current codebase, CPFA already has a global `PheromoneList` inside `CPFA_loop_functions`, and `CPFA_controller::SetTargetPheromone()` selects targets from that global list. The current `Returning()` logic only creates and pushes a pheromone into `LoopFunctions->PheromoneList` after the robot reaches the nest, which is exactly the central-server behavior the project wants to replace.   

The good news is that the codebase already has a usable `Pheromone` concept: it stores waypoint location, trail, creation/update time, decay rate, resource density, weight, and active/inactive threshold behavior. The MVP can reuse or wrap that logic rather than inventing a completely new pheromone model. 

---

# Recommended approach: create a separate DCPFA plugin

Do **not** modify `source/CPFA/*` directly. Treat the original CPFA as the baseline implementation and create a new sibling implementation:

```text
source/
  CPFA/        # untouched original baseline
  Base/        # reused, not modified
  DCPFA/       # new decentralized CPFA implementation
```

The only existing-codebase edit should be one small build-system hook:

```cmake
# source/CMakeLists.txt
add_subdirectory(DCPFA)
```

Everything else should be new files. This keeps the project code clearly separated and avoids confusion between original CPFA behavior and decentralized CPFA behavior.

---

## Proposed new file structure

```text
source/DCPFA/
  CMakeLists.txt

  DCPFA_controller.h
  DCPFA_controller.cpp

  DCPFA_loop_functions.h
  DCPFA_loop_functions.cpp

  DCPFA_qt_user_functions.h
  DCPFA_qt_user_functions.cpp

  DecentralizedPheromone.h
  DecentralizedPheromone.cpp

  RobotPheromoneMemory.h
  RobotPheromoneMemory.cpp

  LocalCommNetwork.h
  LocalCommNetwork.cpp

experiments/dcpfa_mvp/
  DCPFA_Random_24r_256tags_10x10.xml
  DCPFA_Powerlaw_24r_256tags_10x10.xml
  DCPFA_Clustered_24r_256tags_10x10.xml

  CPFA_Baseline_Random_24r_256tags_10x10.xml
  CPFA_Baseline_Powerlaw_24r_256tags_10x10.xml
  CPFA_Baseline_Clustered_24r_256tags_10x10.xml

tools/dcpfa/
  run_mvp_trials.py
  summarize_results.py
  plot_boxplots.py
  patch_cmake_for_dcpfa.sh
  README_DCPFA_MVP.md
```

The `DCPFA_controller` and `DCPFA_loop_functions` files should start as copies of the CPFA controller and loop functions, renamed and registered separately. This is cleaner than subclassing because the existing CPFA controller has the state machine and helper methods as private implementation details, so subclassing would force edits to the original headers.

---

# Phase 0 — Baseline reproduction and experiment setup

**Goal:** Establish a clean baseline before changing behavior.

Create the six XML files under `experiments/dcpfa_mvp/`: three original CPFA baseline XMLs and three DCPFA XMLs. Do not overwrite the existing XML files in `experiments/`.

The project-required settings should be reflected in these XMLs:

```text
Arena size:              10 x 10 m
Collection zone radius:  0.25 m
Resources:               256
Robots:                  24
Foraging time:           720 seconds / 12 minutes
Distributions:           Random, Powerlaw, Clustered
Runs per distribution:   50
Communication radius:    2.0 m for DCPFA only
```

One important configuration note: the existing loop function reads `MaxSimTimeInSeconds`, `FoodDistribution`, `FoodItemCount`, `NestRadius`, and related settings from XML, but it also scales `NestRadius` internally based on arena width. Account for that in the copied DCPFA loop or in the MVP XMLs so the *effective* collection zone radius is actually 0.25 m.  

**Deliverables:**

```text
experiments/dcpfa_mvp/CPFA_Baseline_*.xml
experiments/dcpfa_mvp/DCPFA_*.xml
tools/dcpfa/run_mvp_trials.py
```

**Acceptance check:** Running the CPFA baseline XMLs should still produce normal score output. The current `PostExperiment()` already prints score, simulation time, and seed, and also writes final-score result files when enabled, so the runner can parse existing output instead of requiring large code changes. 

---

# Phase 1 — Create isolated DCPFA build target

**Goal:** Create a separate compile target that behaves exactly like CPFA before adding communication.

Steps:

1. Copy `source/CPFA` into `source/DCPFA`.
2. Rename classes and registration labels:

   * `CPFA_controller` → `DCPFA_controller`
   * `CPFA_loop_functions` → `DCPFA_loop_functions`
   * `CPFA_qt_user_functions` → `DCPFA_qt_user_functions`
   * registration strings:

     * `"CPFA_controller"` → `"DCPFA_controller"`
     * `"CPFA_loop_functions"` → `"DCPFA_loop_functions"`
3. Create `source/DCPFA/CMakeLists.txt`.
4. Link against existing `BaseController`, `Pheromone`, and `Nest`.
5. Add only this line to `source/CMakeLists.txt`:

```cmake
add_subdirectory(DCPFA)
```

6. Keep `build.sh` unchanged.

**Deliverables:**

```text
source/DCPFA/CMakeLists.txt
source/DCPFA/DCPFA_controller.{h,cpp}
source/DCPFA/DCPFA_loop_functions.{h,cpp}
source/DCPFA/DCPFA_qt_user_functions.{h,cpp}
```

**Acceptance check:** With decentralized sharing disabled, `DCPFA_*` should compile and run like CPFA for the same seed. This proves the separate plugin works before adding new behavior.

---

# Phase 2 — Add local pheromone memory per robot

**Goal:** Move pheromone ownership from the global loop-function list into each robot.

Add two new files:

```text
source/DCPFA/DecentralizedPheromone.h
source/DCPFA/DecentralizedPheromone.cpp
source/DCPFA/RobotPheromoneMemory.h
source/DCPFA/RobotPheromoneMemory.cpp
```

`DecentralizedPheromone` should hold:

```cpp
std::string id;              // unique waypoint id
std::string origin_robot_id;
argos::CVector2 location;
std::vector<argos::CVector2> trail;
argos::Real created_time;
argos::Real last_updated_time;
argos::Real decay_rate;
argos::Real weight;
argos::Real threshold;
size_t resource_density;
size_t hop_count;
```

The ID should be deterministic enough to prevent duplicate copies when messages are relayed:

```text
origin_robot_id + creation_tick + quantized_x + quantized_y
```

`RobotPheromoneMemory` should expose:

```cpp
void AddLocalPheromone(...);
bool ReceivePheromone(const DecentralizedPheromone& msg);
std::vector<DecentralizedPheromone> ExportActivePheromones() const;
void DecayAndPrune(argos::Real current_time);
bool SelectTarget(argos::CRandom::CRNG* rng, argos::CVector2& target_out);
size_t Size() const;
```

The existing `Pheromone` class already decays weight and marks pheromones inactive below threshold, so this new class can either wrap `Pheromone` or mirror its decay behavior with added metadata. The wrapper approach is safer, but mirroring may be cleaner because the MVP needs IDs, origin robot IDs, hop counts, and merge rules that `Pheromone` does not currently store. 

**Acceptance check:** A small non-ARGoS test can create a pheromone, decay it, receive it twice, verify no duplicates, and verify deletion below threshold.

---

# Phase 3 — Add the local communication network

**Goal:** Simulate direct robot-to-robot communication within 2 m without using a central pheromone server.

Add:

```text
source/DCPFA/LocalCommNetwork.h
source/DCPFA/LocalCommNetwork.cpp
```

The loop function can still *coordinate* the simulation of communication because ARGoS loop functions can inspect robot positions, but it should **not store pheromone knowledge as global truth**. Each robot owns its own pheromone memory.

Recommended loop-level pseudocode:

```cpp
void DCPFA_loop_functions::DecentralizedCommunicationStep() {
    auto robots = GetAllDCPFARobotControllers();

    for each robot:
        robot.DecayAndPrunePheromoneMemory(current_time);

    for each pair (i, j):
        if DistanceSquared(robot_i.position, robot_j.position) <= 4.0:
            auto i_msgs = robot_i.ExportActivePheromones();
            auto j_msgs = robot_j.ExportActivePheromones();

            robot_i.ReceivePheromones(j_msgs);
            robot_j.ReceivePheromones(i_msgs);
}
```

Run this on a fixed interval, probably every 0.5 seconds, matching the existing pheromone update cadence in CPFA. The original CPFA loop already updates pheromones on half-second intervals, so using the same timing keeps behavior comparable. 

Add these DCPFA-only XML settings:

```xml
<communication
  EnableDecentralizedSharing="1"
  CommunicationRadius="2.0"
  CommunicationPeriodSeconds="0.5"
  MaxPheromonesPerRobot="128"
  DebugCommunication="0"/>
```

**Acceptance check:** In a simple 3-robot test, robot A shares with robot B when within 2 m, robot C receives nothing until it comes within 2 m of A or B, and B can relay A’s pheromone to C.

---

# Phase 4 — Integrate communication into DCPFA behavior

**Goal:** Change DCPFA behavior while leaving original CPFA untouched.

### 4.1 On resource discovery

In copied `DCPFA_controller::SetLocalResourceDensity()`, create a local pheromone immediately after the robot finds food and computes resource density. The original CPFA records `SiteFidelityPosition`, `ResourceDensity`, and trail information at food pickup; this is the right hook for MVP creation. 

New behavior:

```text
Robot finds resource
→ calculate resource density
→ create local DecentralizedPheromone
→ store in robot’s RobotPheromoneMemory
→ robot continues toward nest to drop off resource
→ while returning, it shares the active local cache with nearby robots
```

This matches the PDF requirement that a robot creates a waypoint when it finds a resource and starts sharing it on the way back to the center. 

### 4.2 During return-to-nest

Do **not** wait until nest arrival to push into `LoopFunctions->PheromoneList`.

In DCPFA, remove or disable this copied central behavior:

```cpp
LoopFunctions->PheromoneList.push_back(sharedPheromone);
```

Do not delete it from original CPFA. Only remove/disable it in `DCPFA_controller.cpp`.

### 4.3 Target selection

Replace copied `DCPFA_controller::SetTargetPheromone()` so it samples from the robot’s own `RobotPheromoneMemory`, not from `LoopFunctions->PheromoneList`.

Current CPFA target selection samples from the global `LoopFunctions->PheromoneList`, which is exactly the central sharing pattern. 

New DCPFA logic:

```text
At departure decision:
1. Try local site fidelity.
2. Else try local pheromone memory.
3. Else random search.
```

That preserves the CPFA decision pattern but changes the pheromone source from global server to local memory.

### 4.4 Relay received waypoints

Every robot should export all active pheromones in its memory, not only pheromones it created. That satisfies the requirement that received waypoint information can be shared onward. 

**Acceptance check:** A robot that never found food can still later guide its search using a pheromone received from another robot.

---

# Phase 5 — Evaluation harness and result isolation

**Goal:** Run the required experiments without mixing DCPFA results with CPFA results.

Create:

```text
tools/dcpfa/run_mvp_trials.py
tools/dcpfa/summarize_results.py
tools/dcpfa/plot_boxplots.py
```

`run_mvp_trials.py` should:

1. Accept algorithm: `cpfa` or `dcpfa`.
2. Accept distribution: `random`, `powerlaw`, `clustered`.
3. Run 50 seeds.
4. Create temporary XML copies with seed injected.
5. Run:

```bash
argos3 -n -c experiments/dcpfa_mvp/<xml_file>
```

6. Parse the final output line:

```text
score, sim_time, seed
```

The existing GA runner already parses ARGoS output this way, so the same approach can be reused in a separate script. 

Write results to a new file only:

```text
results/dcpfa_mvp/raw_results.csv
```

Suggested columns:

```text
algorithm,distribution,run,seed,score,sim_time_seconds,communication_radius,
messages_sent,messages_received,final_avg_cache_size
```

For the final report:

```text
improvement_percent =
100 * (mean(DCPFA_collected) - mean(CPFA_collected)) / mean(CPFA_collected)
```

Produce:

```text
results/dcpfa_mvp/boxplot_by_distribution.png
results/dcpfa_mvp/improvement_summary.csv
results/dcpfa_mvp/report_notes.md
```

**Acceptance check:** There should be 300 total runs:

```text
3 distributions × 50 CPFA baseline runs = 150
3 distributions × 50 DCPFA runs         = 150
```

---

# Phase 6 — MVP tuning without changing the original CPFA

**Goal:** Improve score while keeping the implementation understandable.

Tune only DCPFA-specific settings first:

```text
CommunicationPeriodSeconds
MaxPheromonesPerRobot
pheromone merge rule
pheromone selection weight
cache pruning strategy
```

Do **not** immediately retune CPFA’s evolved behavioral parameters unless there is time after the MVP is stable. The initial comparison should use the same CPFA parameters so the reported gain is attributable to decentralized sharing rather than unrelated parameter tuning.

Recommended DCPFA selection weight:

```text
selection_weight = pheromone_weight * max(1, resource_density)
```

Recommended merge rule:

```text
If incoming id does not exist:
    insert it.
If incoming id exists:
    keep the copy with higher current weight or newer last_updated_time.
```

Recommended cache cap:

```text
MaxPheromonesPerRobot = 128
When over cap:
    drop inactive first,
    then lowest-weight oldest pheromones.
```

This prevents message flooding while still allowing multi-hop spread.

---

# Minimal existing-file edit list

The plan should keep the actual codebase edits to this:

```text
Modified existing files:
  source/CMakeLists.txt
    + add_subdirectory(DCPFA)

Unmodified existing files:
  source/CPFA/*
  source/Base/*
  existing experiments/*
  build.sh
  ga.py
```

All project-specific logic lives here:

```text
source/DCPFA/*
experiments/dcpfa_mvp/*
tools/dcpfa/*
results/dcpfa_mvp/*
```

That gives a clean separation:

```text
CPFA  = original centralized baseline
DCPFA = project MVP decentralized communication implementation
```

---

# MVP acceptance criteria

The MVP is complete when all of these are true:

1. **Build isolation:** Original CPFA still builds and runs unchanged.
2. **Separate DCPFA plugin:** DCPFA builds as its own controller and loop-function library.
3. **No global pheromone server:** DCPFA target selection does not read from `LoopFunctions->PheromoneList`.
4. **Local robot memory:** Each robot maintains its own pheromone cache.
5. **2 m communication radius:** Pheromones are exchanged only between robots whose positions are within 2 m.
6. **Relay behavior:** Robots forward pheromones they received, not only pheromones they created.
7. **Decay and deletion:** Each robot decays and prunes its own pheromone memory.
8. **Resource discovery trigger:** A robot creates a waypoint when it finds food and begins sharing it while returning to the collection zone.
9. **Evaluation:** 50 runs each for Random, Powerlaw, and Clustered distributions.
10. **Report:** Box plots plus percentage improvement in collected resources over original CPFA.

This plan keeps the original CPFA implementation intact, adds a clearly named decentralized variant, and makes the MVP easy to explain, test, and compare against the baseline.
