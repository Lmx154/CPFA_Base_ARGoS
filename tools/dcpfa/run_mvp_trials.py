#!/usr/bin/env python3
"""Run the official CPFA vs DCPFA MVP trials and summarize improvement."""

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "tools" / "dcpfa" / "official_experiments.csv"
DEFAULT_RESULTS = ROOT / "results" / "dcpfa_mvp"
RAW_FIELDS = [
    "algorithm",
    "distribution",
    "trial",
    "configured_seed",
    "reported_seed",
    "score",
    "sim_time_s",
    "xml",
    "returncode",
    "duration_s",
]


@dataclass(frozen=True)
class TrialTask:
    algorithm: str
    distribution: str
    xml: str
    trial: int
    seed: int


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS))
    parser.add_argument("--trials", type=int, default=None, help="override manifest trial count")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--base-seed", type=int, default=100000)
    parser.add_argument("--resume", action="store_true", help="skip completed raw result rows")
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def load_manifest(path, trial_override):
    rows = []
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            row["trials"] = trial_override if trial_override is not None else int(row["trials"])
            rows.append(row)
    return rows


def distribution_offset(distribution):
    offsets = {
        "Random": 0,
        "Powerlaw": 10000,
        "Clustered": 20000,
    }
    return offsets[distribution]


def build_tasks(manifest_rows, base_seed):
    tasks = []
    for row in manifest_rows:
        for trial in range(1, int(row["trials"]) + 1):
            tasks.append(
                TrialTask(
                    algorithm=row["algorithm"],
                    distribution=row["distribution"],
                    xml=row["xml"],
                    trial=trial,
                    seed=base_seed + distribution_offset(row["distribution"]) + trial,
                )
            )
    return tasks


def existing_keys(raw_path):
    if not raw_path.exists():
        return set()
    with raw_path.open(newline="") as handle:
        return {
            (row["algorithm"], row["distribution"], int(row["trial"]))
            for row in csv.DictReader(handle)
            if row.get("returncode") == "0"
        }


def patch_seed(xml_path, seed):
    tree = ET.parse(xml_path)
    experiment = tree.find("./framework/experiment")
    if experiment is None:
        raise ValueError(f"{xml_path} is missing framework/experiment")
    experiment.set("random_seed", str(seed))

    temp = tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".xml",
        prefix="dcpfa_trial_",
        dir=str(ROOT / "experiments"),
        delete=False,
    )
    tree.write(temp, encoding="utf-8", xml_declaration=True)
    temp.close()
    return Path(temp.name)


def parse_score(stdout):
    for line in reversed(stdout.strip().splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 3:
            try:
                return float(parts[0]), float(parts[1]), int(parts[2])
            except ValueError:
                continue
    raise ValueError("could not parse ARGoS score line")


def run_trial(task):
    start = time.time()
    temp_xml = patch_seed(ROOT / task.xml, task.seed)
    try:
        completed = subprocess.run(
            ["argos3", "-n", "-c", str(temp_xml)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        duration = time.time() - start
        if completed.returncode != 0:
            return {
                "algorithm": task.algorithm,
                "distribution": task.distribution,
                "trial": task.trial,
                "configured_seed": task.seed,
                "reported_seed": "",
                "score": "",
                "sim_time_s": "",
                "xml": task.xml,
                "returncode": completed.returncode,
                "duration_s": f"{duration:.3f}",
            }

        score, sim_time, reported_seed = parse_score(completed.stdout)
        return {
            "algorithm": task.algorithm,
            "distribution": task.distribution,
            "trial": task.trial,
            "configured_seed": task.seed,
            "reported_seed": reported_seed,
            "score": f"{score:.6f}",
            "sim_time_s": f"{sim_time:.6f}",
            "xml": task.xml,
            "returncode": 0,
            "duration_s": f"{duration:.3f}",
        }
    finally:
        temp_xml.unlink(missing_ok=True)


def percentile(values, p):
    sorted_values = sorted(values)
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def summarize(raw_path, summary_path):
    grouped = {}
    with raw_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["returncode"] != "0":
                continue
            key = (row["distribution"], row["algorithm"])
            grouped.setdefault(key, []).append(float(row["score"]))

    summary_rows = []
    distributions = ["Random", "Powerlaw", "Clustered"]
    for distribution in distributions:
        cpfa = grouped.get((distribution, "CPFA"), [])
        dcpfa = grouped.get((distribution, "DCPFA"), [])
        for algorithm, values in (("CPFA", cpfa), ("DCPFA", dcpfa)):
            if values:
                summary_rows.append(
                    {
                        "distribution": distribution,
                        "algorithm": algorithm,
                        "n": len(values),
                        "mean_score": f"{statistics.mean(values):.6f}",
                        "median_score": f"{statistics.median(values):.6f}",
                        "stdev_score": f"{statistics.stdev(values):.6f}" if len(values) > 1 else "0.000000",
                        "min_score": f"{min(values):.6f}",
                        "max_score": f"{max(values):.6f}",
                        "improvement_percent": "",
                    }
                )
        if cpfa and dcpfa:
            cpfa_mean = statistics.mean(cpfa)
            dcpfa_mean = statistics.mean(dcpfa)
            improvement = 100.0 * (dcpfa_mean - cpfa_mean) / cpfa_mean if cpfa_mean else 0.0
            summary_rows.append(
                {
                    "distribution": distribution,
                    "algorithm": "DCPFA_vs_CPFA",
                    "n": min(len(cpfa), len(dcpfa)),
                    "mean_score": f"{dcpfa_mean:.6f}",
                    "median_score": "",
                    "stdev_score": "",
                    "min_score": "",
                    "max_score": "",
                    "improvement_percent": f"{improvement:.6f}",
                }
            )

    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "distribution",
                "algorithm",
                "n",
                "mean_score",
                "median_score",
                "stdev_score",
                "min_score",
                "max_score",
                "improvement_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    return grouped, summary_rows


def draw_text(draw, position, text, fill=(20, 20, 20)):
    draw.text(position, text, fill=fill, font=ImageFont.load_default())


def plot_boxplots(grouped, output_path):
    width, height = 1200, 720
    margin_left, margin_right = 90, 40
    margin_top, margin_bottom = 70, 120
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    all_values = [value for values in grouped.values() for value in values]
    if not all_values:
        raise ValueError("no data to plot")
    y_min = max(0.0, min(all_values) - 5.0)
    y_max = max(all_values) + 5.0
    if y_max <= y_min:
        y_max = y_min + 1.0

    plot_left = margin_left
    plot_right = width - margin_right
    plot_top = margin_top
    plot_bottom = height - margin_bottom

    def y_to_px(value):
        return plot_bottom - int((value - y_min) / (y_max - y_min) * (plot_bottom - plot_top))

    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=(0, 0, 0), width=2)
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=(0, 0, 0), width=2)
    draw_text(draw, (plot_left, 25), "CPFA vs DCPFA Collected Resources by Distribution")

    ticks = 5
    for idx in range(ticks + 1):
        value = y_min + (y_max - y_min) * idx / ticks
        y = y_to_px(value)
        draw.line((plot_left - 5, y, plot_right, y), fill=(230, 230, 230))
        draw_text(draw, (10, y - 7), f"{value:.0f}")

    distributions = ["Random", "Powerlaw", "Clustered"]
    colors = {"CPFA": (74, 122, 184), "DCPFA": (219, 128, 57)}
    group_width = (plot_right - plot_left) / len(distributions)
    box_width = 70

    for dist_index, distribution in enumerate(distributions):
        center = plot_left + group_width * (dist_index + 0.5)
        draw_text(draw, (int(center - 45), plot_bottom + 55), distribution)
        for alg_index, algorithm in enumerate(["CPFA", "DCPFA"]):
            values = grouped.get((distribution, algorithm), [])
            if not values:
                continue
            x = int(center + (-45 if algorithm == "CPFA" else 45))
            q1 = percentile(values, 0.25)
            med = percentile(values, 0.50)
            q3 = percentile(values, 0.75)
            low = min(values)
            high = max(values)
            mean = statistics.mean(values)

            color = colors[algorithm]
            draw.line((x, y_to_px(low), x, y_to_px(high)), fill=color, width=3)
            draw.line((x - 18, y_to_px(low), x + 18, y_to_px(low)), fill=color, width=3)
            draw.line((x - 18, y_to_px(high), x + 18, y_to_px(high)), fill=color, width=3)
            draw.rectangle(
                (x - box_width // 2, y_to_px(q3), x + box_width // 2, y_to_px(q1)),
                outline=color,
                fill=tuple(min(255, c + 55) for c in color),
                width=3,
            )
            draw.line((x - box_width // 2, y_to_px(med), x + box_width // 2, y_to_px(med)), fill=(0, 0, 0), width=3)
            draw.ellipse((x - 4, y_to_px(mean) - 4, x + 4, y_to_px(mean) + 4), fill=(0, 0, 0))
            draw_text(draw, (x - 22, plot_bottom + 22), algorithm)

    legend_x = plot_right - 190
    for index, algorithm in enumerate(["CPFA", "DCPFA"]):
        y = 30 + index * 24
        draw.rectangle((legend_x, y, legend_x + 18, y + 14), fill=colors[algorithm])
        draw_text(draw, (legend_x + 26, y - 1), algorithm)
    draw_text(draw, (plot_left, height - 35), "Box = IQR, line = median, dot = mean, whiskers = min/max")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def write_rows(raw_path, rows):
    file_exists = raw_path.exists()
    with raw_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS)
        if not file_exists or raw_path.stat().st_size == 0:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
        handle.flush()


def build_if_needed(skip_build):
    if skip_build:
        return
    subprocess.run(["cmake", "--build", "build"], cwd=str(ROOT), check=True)


def main():
    args = parse_args()
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    raw_path = results_dir / "raw_results.csv"
    summary_path = results_dir / "improvement_summary.csv"
    plot_path = results_dir / "boxplot_by_distribution.png"

    build_if_needed(args.skip_build)

    manifest_rows = load_manifest(args.manifest, args.trials)
    tasks = build_tasks(manifest_rows, args.base_seed)
    if args.resume:
        done = existing_keys(raw_path)
        tasks = [
            task
            for task in tasks
            if (task.algorithm, task.distribution, task.trial) not in done
        ]

    print(f"Running {len(tasks)} trials with {args.workers} worker(s)", flush=True)
    completed_count = 0
    total_count = len(tasks)
    start = time.time()

    if args.workers <= 1:
        for task in tasks:
            row = run_trial(task)
            write_rows(raw_path, [row])
            completed_count += 1
            print(
                f"[{completed_count}/{total_count}] {row['algorithm']} {row['distribution']} "
                f"trial {row['trial']} score={row['score']} seed={row['reported_seed']}",
                flush=True,
            )
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(run_trial, task) for task in tasks]
            for future in as_completed(futures):
                row = future.result()
                write_rows(raw_path, [row])
                completed_count += 1
                print(
                    f"[{completed_count}/{total_count}] {row['algorithm']} {row['distribution']} "
                    f"trial {row['trial']} score={row['score']} seed={row['reported_seed']}",
                    flush=True,
                )

    failed = []
    if raw_path.exists():
        with raw_path.open(newline="") as handle:
            failed = [row for row in csv.DictReader(handle) if row["returncode"] != "0"]
    if failed:
        print(f"FAIL: {len(failed)} trial(s) failed; see {raw_path}", file=sys.stderr)
        return 1

    grouped, summary_rows = summarize(raw_path, summary_path)
    plot_boxplots(grouped, plot_path)

    elapsed = time.time() - start
    print(f"Finished in {elapsed:.1f}s", flush=True)
    print(f"Wrote {raw_path}", flush=True)
    print(f"Wrote {summary_path}", flush=True)
    print(f"Wrote {plot_path}", flush=True)
    for row in summary_rows:
        if row["algorithm"] == "DCPFA_vs_CPFA":
            print(
                f"{row['distribution']}: DCPFA improvement = "
                f"{row['improvement_percent']}%",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
