#!/usr/bin/env python3
"""Validate the six official CPFA/DCPFA MVP experiment XMLs."""

import math
import csv
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = ROOT / "experiments" / "dcpfa_mvp"
MANIFEST = ROOT / "tools" / "dcpfa" / "official_experiments.csv"

EXPECTED = {
    "CPFA_Baseline_Random_24r_256tags_10x10.xml": ("CPFA", 0),
    "CPFA_Baseline_Powerlaw_24r_256tags_10x10.xml": ("CPFA", 2),
    "CPFA_Baseline_Clustered_24r_256tags_10x10.xml": ("CPFA", 1),
    "DCPFA_Random_24r_256tags_10x10.xml": ("DCPFA", 0),
    "DCPFA_Powerlaw_24r_256tags_10x10.xml": ("DCPFA", 2),
    "DCPFA_Clustered_24r_256tags_10x10.xml": ("DCPFA", 1),
}


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def parse_vector(value):
    return [float(part.strip()) for part in value.split(",")]


def as_int(element, attribute):
    return int(element.attrib[attribute])


def as_float(element, attribute):
    return float(element.attrib[attribute])


def effective_nest_radius(xml_radius, arena_width, nest_position):
    if abs(nest_position[0]) < -1:
        return xml_radius * math.sqrt(1.0 + math.log(arena_width) / math.log(2.0))
    return xml_radius * math.sqrt(math.log(arena_width) / math.log(2.0))


def validate_file(path, algorithm, distribution):
    tree = ET.parse(path)
    root = tree.getroot()
    errors = []

    experiment = root.find("./framework/experiment")
    if experiment is None:
        errors.append("missing framework/experiment")
    else:
        if as_int(experiment, "length") != 720:
            errors.append("experiment length is not 720 seconds")
        if as_int(experiment, "ticks_per_second") != 32:
            errors.append("ticks_per_second is not 32")

    loop = root.find("./loop_functions")
    if loop is None:
        errors.append("missing loop_functions")
        return errors

    expected_label = f"{algorithm}_loop_functions"
    if loop.attrib.get("label") != expected_label:
        errors.append(f"loop_functions label is not {expected_label}")

    settings = loop.find("settings")
    if settings is None:
        errors.append("missing loop settings")
        return errors

    if as_int(settings, "MaxSimTimeInSeconds") != 720:
        errors.append("MaxSimTimeInSeconds is not 720")
    if as_int(settings, "FoodDistribution") != distribution:
        errors.append(f"FoodDistribution is not {distribution}")
    if as_int(settings, "FoodItemCount") != 256:
        errors.append("FoodItemCount is not 256")
    if as_int(settings, "MaxSimCounter") != 1:
        errors.append("MaxSimCounter should be 1; use the Phase G runner for 50 trials")

    number_of_clusters = as_int(settings, "NumberOfClusters")
    cluster_width_x = as_int(settings, "ClusterWidthX")
    cluster_width_y = as_int(settings, "ClusterWidthY")
    if distribution == 1 and number_of_clusters * cluster_width_x * cluster_width_y != 256:
        errors.append("clustered distribution does not create 256 resources")

    arena = root.find("./arena")
    if arena is None:
        errors.append("missing arena")
        return errors

    arena_size = parse_vector(arena.attrib["size"])
    if len(arena_size) < 2 or not (math.isclose(arena_size[0], 10.0) and math.isclose(arena_size[1], 10.0)):
        errors.append("arena is not 10 x 10 m")

    nest_position = parse_vector(settings.attrib["NestPosition"])
    actual_nest_radius = effective_nest_radius(
        as_float(settings, "NestRadius"), arena_size[0], nest_position
    )
    if not math.isclose(actual_nest_radius, 0.25, abs_tol=0.002):
        errors.append(f"effective nest radius is {actual_nest_radius:.6f}, not 0.25")

    robot_count = 0
    wrong_controllers = []
    for entity in arena.findall("./distribute/entity"):
        robot_count += as_int(entity, "quantity")
        controller = entity.find("./foot-bot/controller")
        if controller is None or controller.attrib.get("config") != algorithm:
            wrong_controllers.append(controller.attrib.get("config") if controller is not None else "missing")

    if robot_count != 24:
        errors.append(f"robot quantity is {robot_count}, not 24")
    if wrong_controllers:
        errors.append("robot controllers do not all use " + algorithm)

    communication = loop.find("communication")
    if algorithm == "DCPFA":
        if communication is None:
            errors.append("DCPFA XML is missing communication settings")
        else:
            if as_int(communication, "EnableDecentralizedSharing") != 1:
                errors.append("DCPFA communication is not enabled")
            if not math.isclose(as_float(communication, "CommunicationRadius"), 2.0):
                errors.append("DCPFA CommunicationRadius is not 2.0")
    elif communication is not None:
        errors.append("CPFA baseline should not include DCPFA communication settings")

    return errors


def main():
    all_errors = {}

    for filename, (algorithm, distribution) in EXPECTED.items():
        path = EXPERIMENT_DIR / filename
        if not path.exists():
            all_errors[filename] = ["file is missing"]
            continue
        errors = validate_file(path, algorithm, distribution)
        if errors:
            all_errors[filename] = errors

    extra_official = sorted(
        path.name
        for path in EXPERIMENT_DIR.glob("*24r_256tags_10x10.xml")
        if path.name not in EXPECTED
    )
    if extra_official:
        all_errors["unexpected XMLs"] = extra_official

    if not MANIFEST.exists():
        all_errors["official_experiments.csv"] = ["manifest is missing"]
    else:
        with MANIFEST.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        manifest_xmls = {Path(row["xml"]).name: row for row in rows}
        if set(manifest_xmls) != set(EXPECTED):
            all_errors["official_experiments.csv"] = [
                "manifest does not list exactly the six official XMLs"
            ]
        else:
            manifest_errors = []
            for filename, (algorithm, distribution) in EXPECTED.items():
                row = manifest_xmls[filename]
                if row["algorithm"] != algorithm:
                    manifest_errors.append(f"{filename} algorithm is not {algorithm}")
                if int(row["trials"]) != 50:
                    manifest_errors.append(f"{filename} trial count is not 50")
                expected_distribution_name = {
                    0: "Random",
                    1: "Clustered",
                    2: "Powerlaw",
                }[distribution]
                if row["distribution"] != expected_distribution_name:
                    manifest_errors.append(
                        f"{filename} distribution is not {expected_distribution_name}"
                    )
            if manifest_errors:
                all_errors["official_experiments.csv"] = manifest_errors

    if all_errors:
        for filename, errors in all_errors.items():
            print(f"FAIL: {filename}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        return 1

    print("PASS: found six official CPFA/DCPFA MVP XMLs")
    print("PASS: each XML uses a 10 x 10 m arena, 24 robots, 256 resources, and 720 seconds")
    print("PASS: effective nest radius is 0.25 m in every official XML")
    print("PASS: DCPFA XMLs enable 2.0 m decentralized communication")
    print("PASS: CPFA baseline XMLs remain communication-free")
    print("PASS: manifest lists 50 trials per algorithm/distribution")
    return 0


if __name__ == "__main__":
    sys.exit(main())
