#!/usr/bin/env python3
"""Validate DCPFA communication logs against the MVP invariants."""

import argparse
import csv
from pathlib import Path
import subprocess
import sys


def extract_function(text, signature):
    start = text.find(signature)
    if start < 0:
        return ""

    brace_start = text.find("{", start)
    if brace_start < 0:
        return ""

    depth = 0
    for index in range(brace_start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log",
        default="results/dcpfa_mvp/logs/communication_events.csv",
        help="communication_events.csv path",
    )
    parser.add_argument("--radius", type=float, default=2.0)
    parser.add_argument("--source-root", default=".")
    parser.add_argument(
        "--allow-no-relay",
        action="store_true",
        help="do not fail if this stochastic run did not produce an accepted relay",
    )
    parser.add_argument(
        "--skip-memory-test",
        action="store_true",
        help="skip the RobotPheromoneMemory smoke test",
    )
    return parser.parse_args()


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def load_rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def check_required_columns(rows):
    expected_columns = [
        "sim_time_s",
        "sender_id",
        "receiver_id",
        "distance_m",
        "accepted",
        "event_type",
        "pheromone_id",
        "origin_robot_id",
        "hop_count",
        "sender_cache_size",
        "receiver_cache_size_before",
        "receiver_cache_size_after",
    ]
    missing = [column for column in expected_columns if column not in rows[0]]
    return missing


def run_memory_smoke_test(source_root):
    script = source_root / "tools" / "dcpfa" / "test_pheromone_memory.sh"
    if not script.exists():
        return False, f"memory smoke test not found: {script}"

    result = subprocess.run(
        ["bash", str(script)],
        cwd=str(source_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip()
    return True, result.stdout.strip()


def check_controller_does_not_share_via_global_list(source_root):
    controller = source_root / "source" / "DCPFA" / "DCPFA_controller.cpp"
    text = controller.read_text()
    forbidden = ("LoopFunctions->PheromoneList", "PheromoneList.push_back")
    return [token for token in forbidden if token in text]


def check_phase_c_source_invariants(source_root):
    controller = source_root / "source" / "DCPFA" / "DCPFA_controller.cpp"
    text = controller.read_text()
    failures = []

    set_density = extract_function(text, "void DCPFA_controller::SetLocalResourceDensity()")
    if "PheromoneMemory.AddLocalPheromone" not in set_density:
        failures.append("resource discovery does not create a local pheromone")

    returning = extract_function(text, "void DCPFA_controller::Returning()")
    if "AddLocalPheromone" in returning:
        failures.append("Returning() still creates pheromones at nest arrival")

    target_pheromone = extract_function(text, "bool DCPFA_controller::SetTargetPheromone()")
    if "PheromoneMemory.SelectTarget" not in target_pheromone:
        failures.append("pheromone target selection does not use local memory")

    site_index = returning.find("poissonCDF_sFollowRate")
    pheromone_index = returning.find("SetTargetPheromone()")
    random_index = returning.find("SetRandomSearchLocation()")
    if not (0 <= site_index < pheromone_index < random_index):
        failures.append("target priority is not site fidelity -> local pheromone -> random")

    return failures


def check_phase_d_source_invariants(source_root):
    loop_functions = source_root / "source" / "DCPFA" / "DCPFA_loop_functions.cpp"
    text = loop_functions.read_text()
    communication = extract_function(
        text, "void DCPFA_loop_functions::DecentralizedCommunicationStep()"
    )
    failures = []

    expected_tokens = {
        "DecayAndPrunePheromoneMemory": "robots do not decay/prune local memory in the communication step",
        "CommunicationRadiusSquared": "communication step does not enforce the configured radius",
        "ExportActivePheromones": "communication step does not export robot-local pheromones",
        "ReceivePheromones": "communication step does not deliver pheromones to receivers",
        "hop_count++": "communication step does not increment hop counts for relay proof",
    }
    for token, message in expected_tokens.items():
        if token not in communication:
            failures.append(message)

    return failures


def main():
    args = parse_args()
    log_path = Path(args.log)
    source_root = Path(args.source_root)

    if not log_path.exists():
        return fail(f"log file not found: {log_path}")

    forbidden_global_uses = check_controller_does_not_share_via_global_list(source_root)
    if forbidden_global_uses:
        return fail(
            "DCPFA_controller still references global pheromone sharing: "
            + ", ".join(forbidden_global_uses)
        )

    phase_c_failures = check_phase_c_source_invariants(source_root)
    if phase_c_failures:
        return fail("Phase C source invariant failed: " + "; ".join(phase_c_failures))

    phase_d_failures = check_phase_d_source_invariants(source_root)
    if phase_d_failures:
        return fail("Phase D source invariant failed: " + "; ".join(phase_d_failures))

    rows = load_rows(log_path)
    if not rows:
        return fail("communication log has no events")

    missing_columns = check_required_columns(rows)
    if missing_columns:
        return fail("communication log missing columns: " + ", ".join(missing_columns))

    accepted_rows = [row for row in rows if row.get("accepted") == "1"]
    if not accepted_rows:
        return fail("communication log has no accepted pheromone transfers")

    logged_out_of_range = [
        row for row in rows if float(row["distance_m"]) > args.radius + 1e-9
    ]
    if logged_out_of_range:
        worst = max(float(row["distance_m"]) for row in logged_out_of_range)
        return fail(f"logged transfer exceeded {args.radius:.3f} m; max={worst:.6f}")

    out_of_range = [
        row for row in accepted_rows if float(row["distance_m"]) > args.radius + 1e-9
    ]
    if out_of_range:
        worst = max(float(row["distance_m"]) for row in out_of_range)
        return fail(f"accepted transfer exceeded {args.radius:.3f} m; max={worst:.6f}")

    direct_rows = [row for row in accepted_rows if row.get("event_type") == "direct"]
    if not direct_rows:
        return fail("no accepted direct event found")

    relay_rows = [
        row
        for row in accepted_rows
        if row.get("event_type") == "relay" or int(row.get("hop_count", "0")) > 1
    ]
    if not relay_rows and not args.allow_no_relay:
        return fail("no accepted relay event found")

    increased_cache = [
        row
        for row in accepted_rows
        if int(row["receiver_cache_size_after"]) > int(row["receiver_cache_size_before"])
    ]
    if not increased_cache:
        return fail("accepted events did not increase any receiver cache")

    if not args.skip_memory_test:
        memory_ok, memory_output = run_memory_smoke_test(source_root)
        if not memory_ok:
            return fail("memory smoke test failed:\n" + memory_output)

    max_distance = max(float(row["distance_m"]) for row in accepted_rows)
    print("PASS: communication log contains required Phase E columns")
    print(f"PASS: {len(accepted_rows)} accepted transfers")
    print(f"PASS: max accepted distance = {max_distance:.6f} m")
    print(f"PASS: accepted direct transfers = {len(direct_rows)}")
    print(f"PASS: accepted relay transfers = {len(relay_rows)}")
    print("PASS: resource discovery creates robot-local pheromones")
    print("PASS: target priority is site fidelity -> local pheromone -> random")
    print("PASS: communication step exchanges robot-local memory within radius")
    if not args.skip_memory_test:
        print("PASS: expired pheromones are pruned")
        print("PASS: received pheromones can be selected as targets")
    print("PASS: DCPFA_controller does not use global PheromoneList for sharing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
