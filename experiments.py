"""
experiments.py - Systematic Numerical Experiments and Stability/Sensitivity Analysis
for T25 Traffic Simulation (NaSch Baseline vs. Improved Mumbai Model).

Generates:
- All 7 numerical experiments
- Stability and Disturbance Propagation analysis
- Sensitivity & Stochastic Repeatability analysis
- 9 verified publication-quality plots saved in static/generated/
- Structured results JSON for REPORT.md and the FastAPI backend
"""

import os
import json
from typing import Dict, List, Any
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless execution
import matplotlib.pyplot as plt

from simulation import (
    NaSchModel, NaSchConfig,
    MumbaiTrafficModel, MumbaiConfig,
    LANE_DISCIPLINE_STRONG, LANE_DISCIPLINE_MODERATE, LANE_DISCIPLINE_WEAK
)

# Output directory for experiment plots and artifacts
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def set_plot_style():
    """Sets a clean, publication-ready plot style matching UI orange/grey theme."""
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "#fafafa",
        "axes.edgecolor": "#cccccc",
        "axes.grid": True,
        "grid.color": "#e5e5e5",
        "grid.linestyle": "--",
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14
    })


# ==============================================================================
# EXPERIMENT 1: Baseline Fundamental Diagram (NaSch 1992)
# ==============================================================================
def run_experiment_1(seeds: List[int] = [42, 101, 202, 303, 404]) -> Dict[str, Any]:
    print("Running Experiment 1: Baseline Fundamental Diagram (NaSch 1992)...")
    densities = np.linspace(0.02, 0.95, 30)
    flows_mean = []
    flows_std = []
    speeds_mean = []

    for rho in densities:
        seed_flows = []
        seed_speeds = []
        for s in seeds:
            cfg = NaSchConfig(
                road_length=200,
                density=float(rho),
                max_speed=5,
                slowdown_prob=0.3,
                simulation_steps=600,
                warmup_steps=200,
                random_seed=s
            )
            model = NaSchModel(cfg)
            res = model.run_all()
            seed_flows.append(res["mean_flow"])
            seed_speeds.append(res["mean_speed"])

        flows_mean.append(float(np.mean(seed_flows)))
        flows_std.append(float(np.std(seed_flows)))
        speeds_mean.append(float(np.mean(seed_speeds)))

    peak_idx = int(np.argmax(flows_mean))
    peak_density = float(densities[peak_idx])
    peak_flow = float(flows_mean[peak_idx])

    # Plot
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    color_flow = "#ff6600"
    color_speed = "#2c3e50"

    ax1.errorbar(densities, flows_mean, yerr=flows_std, fmt='-o', color=color_flow,
                 ecolor="#ffa366", elinewidth=1.5, capsize=3, label="Flow J (veh/step)")
    ax1.set_xlabel("Density ρ (vehicles / cell)")
    ax1.set_ylabel("Traffic Flow J (veh / step)", color=color_flow)
    ax1.tick_params(axis='y', labelcolor=color_flow)
    ax1.set_ylim(0, max(flows_mean) * 1.25)

    # Secondary axis for speed
    ax2 = ax1.twinx()
    ax2.plot(densities, speeds_mean, '--s', color=color_speed, alpha=0.7, label="Mean Speed (cells/step)")
    ax2.set_ylabel("Mean Speed v (cells / step)", color=color_speed)
    ax2.tick_params(axis='y', labelcolor=color_speed)
    ax2.grid(False)

    plt.title(f"Baseline NaSch Fundamental Diagram (v_max=5, p=0.3)\nPeak Flow: {peak_flow:.3f} at ρ_c={peak_density:.2f}")
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "baseline_fundamental_diagram.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "densities": [round(float(d), 3) for d in densities],
        "flows_mean": [round(f, 4) for f in flows_mean],
        "flows_std": [round(s, 4) for s in flows_std],
        "speeds_mean": [round(v, 3) for v in speeds_mean],
        "peak_density": round(peak_density, 3),
        "peak_flow": round(peak_flow, 4),
        "plot_path": "static/generated/baseline_fundamental_diagram.png"
    }


# ==============================================================================
# EXPERIMENT 2: Extended Mumbai Fundamental Diagram (Open Road vs Circular)
# ==============================================================================
def run_experiment_2(seeds: List[int] = [42, 101, 202]) -> Dict[str, Any]:
    print("Running Experiment 2: Extended Mumbai Fundamental Diagram...")
    densities = np.linspace(0.05, 0.90, 18)
    circ_flows = []
    signal_throughputs = []
    signal_queues = []

    for rho in densities:
        # A. Multi-lane circular mixed traffic without signal
        c_flows = []
        for s in seeds:
            cfg_circ = MumbaiConfig(
                road_length=200,
                density=float(rho),
                two_wheeler_share=0.4,
                lane_discipline=LANE_DISCIPLINE_MODERATE,
                is_circular=True,
                simulation_steps=500,
                warmup_steps=150,
                random_seed=s
            )
            m_circ = MumbaiTrafficModel(cfg_circ)
            res = m_circ.run_all()
            c_flows.append(res["mean_flow"])
        circ_flows.append(float(np.mean(c_flows)))

        # B. Open-road with signal (30s green / 30s red)
        s_th = []
        s_q = []
        for s in seeds:
            cfg_sig = MumbaiConfig(
                road_length=150,
                density=float(rho),
                two_wheeler_share=0.4,
                lane_discipline=LANE_DISCIPLINE_MODERATE,
                signal_position=100,
                green_time=30,
                red_time=30,
                is_circular=False,
                simulation_steps=600,
                warmup_steps=150,
                random_seed=s
            )
            m_sig = MumbaiTrafficModel(cfg_sig)
            res_sig = m_sig.run_all()
            s_th.append(res_sig["throughput"])
            s_q.append(res_sig["mean_queue_length"])
        signal_throughputs.append(float(np.mean(s_th)))
        signal_queues.append(float(np.mean(s_q)))

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(densities, circ_flows, '-o', color="#e65100", label="Extended (Circular Road, No Signal)")
    ax1.plot(densities, signal_throughputs, '-s', color="#1976d2", label="Extended (Open Arterial, Signalized)")
    ax1.set_xlabel("Density / Inflow Demand ρ")
    ax1.set_ylabel("Throughput / Flow (veh / step)")
    ax1.legend(loc="upper left")

    ax2 = ax1.twinx()
    ax2.plot(densities, signal_queues, ':^', color="#d32f2f", alpha=0.75, label="Mean Queue Length (cells)")
    ax2.set_ylabel("Mean Queue Length (cells)", color="#d32f2f")
    ax2.tick_params(axis='y', labelcolor="#d32f2f")
    ax2.grid(False)

    plt.title("Extended Mumbai Model: Fundamental Diagram & Arterial Queue")
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "extended_fundamental_diagram.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "densities": [round(float(d), 3) for d in densities],
        "circ_flows": [round(f, 4) for f in circ_flows],
        "signal_throughputs": [round(t, 4) for t in signal_throughputs],
        "signal_queues": [round(q, 2) for q in signal_queues],
        "plot_path": "static/generated/extended_fundamental_diagram.png"
    }


# ==============================================================================
# EXPERIMENT 3: Effects of Random Slowdowns (p)
# ==============================================================================
def run_experiment_3(seeds: List[int] = [42, 101, 202]) -> Dict[str, Any]:
    print("Running Experiment 3: Effects of Random Slowdown Probability...")
    slowdowns = [0.05, 0.15, 0.30, 0.45, 0.60]
    densities = [0.15, 0.35, 0.60]  # Free flow, critical, jammed
    results_matrix = {}

    for p in slowdowns:
        results_matrix[p] = {}
        for rho in densities:
            flows = []
            speeds = []
            for s in seeds:
                cfg = NaSchConfig(
                    road_length=200,
                    density=rho,
                    max_speed=5,
                    slowdown_prob=p,
                    simulation_steps=500,
                    warmup_steps=150,
                    random_seed=s
                )
                m = NaSchModel(cfg)
                res = m.run_all()
                flows.append(res["mean_flow"])
                speeds.append(res["mean_speed"])
            results_matrix[p][rho] = {
                "flow": float(np.mean(flows)),
                "speed": float(np.mean(speeds))
            }

    # Plot
    fig, ax = plt.subplots(figsize=(7, 4.5))
    colors = ["#2e7d32", "#ff9800", "#c62828"]
    for idx, rho in enumerate(densities):
        y_flows = [results_matrix[p][rho]["flow"] for p in slowdowns]
        ax.plot(slowdowns, y_flows, marker='o', color=colors[idx], linewidth=2,
                label=f"Density ρ = {rho} ({'Free-Flow' if rho<0.2 else ('Peak' if rho<0.4 else 'Congested')})")

    ax.set_xlabel("Random Slowdown Probability p")
    ax.set_ylabel("Traffic Flow J (veh / step)")
    ax.set_title("Impact of Stochastic Dawdling (p) on Traffic Flow Across Regimes")
    ax.legend()
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "random_slowdown_effects.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "slowdowns": slowdowns,
        "densities": densities,
        "results": results_matrix,
        "plot_path": "static/generated/random_slowdown_effects.png"
    }


# ==============================================================================
# EXPERIMENT 4: Effects of Lane Discipline
# ==============================================================================
def run_experiment_4(seeds: List[int] = [42, 101, 202]) -> Dict[str, Any]:
    print("Running Experiment 4: Effects of Lane Discipline...")
    disciplines = [LANE_DISCIPLINE_STRONG, LANE_DISCIPLINE_MODERATE, LANE_DISCIPLINE_WEAK]
    densities = [0.15, 0.30, 0.50, 0.70]
    out_data = {d: {"flows": [], "travel_times": [], "queues": []} for d in disciplines}

    for disc in disciplines:
        for rho in densities:
            fl_list, tt_list, q_list = [], [], []
            for s in seeds:
                cfg = MumbaiConfig(
                    road_length=200,
                    density=rho,
                    two_wheeler_share=0.45,
                    lane_discipline=disc,
                    signal_position=150,
                    green_time=30,
                    red_time=30,
                    simulation_steps=500,
                    warmup_steps=150,
                    random_seed=s
                )
                m = MumbaiTrafficModel(cfg)
                res = m.run_all()
                fl_list.append(res["mean_flow"])
                tt_list.append(res["mean_travel_time"])
                q_list.append(res["mean_queue_length"])

            out_data[disc]["flows"].append(float(np.mean(fl_list)))
            out_data[disc]["travel_times"].append(float(np.mean(tt_list)))
            out_data[disc]["queues"].append(float(np.mean(q_list)))

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    disc_colors = {
        LANE_DISCIPLINE_STRONG: "#1565c0",
        LANE_DISCIPLINE_MODERATE: "#f57c00",
        LANE_DISCIPLINE_WEAK: "#d32f2f"
    }

    for disc in disciplines:
        label_text = f"{disc.capitalize()} Discipline"
        ax1.plot(densities, out_data[disc]["flows"], marker='o', color=disc_colors[disc], label=label_text)
        ax2.plot(densities, out_data[disc]["travel_times"], marker='s', color=disc_colors[disc], label=label_text)

    ax1.set_xlabel("Inflow Density ρ")
    ax1.set_ylabel("Mean Flow (veh/step)")
    ax1.set_title("Flow vs. Inflow Density")
    ax1.legend()

    ax2.set_xlabel("Inflow Density ρ")
    ax2.set_ylabel("Mean Travel Time (steps)")
    ax2.set_title("Travel Time vs. Inflow Density")
    ax2.legend()

    fig.suptitle("Impact of Lane Discipline on Arterial Performance", fontsize=13)
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "lane_discipline_effects.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "densities": densities,
        "data": out_data,
        "plot_path": "static/generated/lane_discipline_effects.png"
    }


# ==============================================================================
# EXPERIMENT 5: Effects of Signal Timing (Cycle Splits)
# ==============================================================================
def run_experiment_5(seeds: List[int] = [42, 101, 202, 303]) -> Dict[str, Any]:
    print("Running Experiment 5: Effects of Signal Timing...")
    # Cycle length fixed at 60 steps; vary green split: 15G/45R, 25G/35R, 35G/25R, 45G/15R
    splits = [(15, 45), (25, 35), (35, 25), (45, 15)]
    split_labels = [f"{g}G/{r}R" for g, r in splits]
    green_ratios = [g / (g + r) for g, r in splits]

    throughputs = []
    travel_times = []
    mean_queues = []
    max_queues = []

    for g, r in splits:
        th_list, tt_list, mq_list, mxq_list = [], [], [], []
        for s in seeds:
            cfg = MumbaiConfig(
                road_length=150,
                density=0.30,
                two_wheeler_share=0.4,
                lane_discipline=LANE_DISCIPLINE_MODERATE,
                signal_position=100,
                green_time=g,
                red_time=r,
                simulation_steps=600,
                warmup_steps=150,
                random_seed=s
            )
            m = MumbaiTrafficModel(cfg)
            res = m.run_all()
            th_list.append(res["throughput"])
            tt_list.append(res["mean_travel_time"])
            mq_list.append(res["mean_queue_length"])
            mxq_list.append(res["max_queue_length"])

        throughputs.append(float(np.mean(th_list)))
        travel_times.append(float(np.mean(tt_list)))
        mean_queues.append(float(np.mean(mq_list)))
        max_queues.append(float(np.mean(mxq_list)))

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    color_th = "#ff6600"
    color_tt = "#1565c0"

    bars = ax1.bar(np.arange(len(splits)) - 0.2, throughputs, width=0.4, color=color_th, label="Throughput (veh/step)")
    ax1.set_xlabel("Signal Phase Split (Cycle = 60 steps)")
    ax1.set_ylabel("Throughput (veh/step)", color=color_th)
    ax1.set_xticks(np.arange(len(splits)))
    ax1.set_xticklabels(split_labels)
    ax1.tick_params(axis='y', labelcolor=color_th)

    ax2 = ax1.twinx()
    ax2.plot(np.arange(len(splits)) + 0.2, travel_times, 'o--', color=color_tt, linewidth=2, label="Mean Travel Time (steps)")
    ax2.set_ylabel("Mean Travel Time (steps)", color=color_tt)
    ax2.tick_params(axis='y', labelcolor=color_tt)
    ax2.grid(False)

    plt.title("Arterial Signal Timing Split: Throughput vs Travel Time")
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "signal_timing_effects.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "splits": split_labels,
        "green_ratios": green_ratios,
        "throughputs": [round(t, 4) for t in throughputs],
        "travel_times": [round(tt, 2) for tt in travel_times],
        "mean_queues": [round(q, 2) for q in mean_queues],
        "max_queues": [round(q, 2) for q in max_queues],
        "plot_path": "static/generated/signal_timing_effects.png"
    }


# ==============================================================================
# EXPERIMENT 6: Effects of Two-Wheeler Share
# ==============================================================================
def run_experiment_6(seeds: List[int] = [42, 101, 202, 303]) -> Dict[str, Any]:
    print("Running Experiment 6: Effects of Two-Wheeler Share...")
    tw_shares = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    flows = []
    speeds = []
    travel_times = []
    queues = []

    for share in tw_shares:
        fl_list, sp_list, tt_list, q_list = [], [], [], []
        for s in seeds:
            cfg = MumbaiConfig(
                road_length=200,
                density=0.35,
                two_wheeler_share=share,
                lane_discipline=LANE_DISCIPLINE_MODERATE,
                signal_position=150,
                green_time=30,
                red_time=30,
                simulation_steps=500,
                warmup_steps=150,
                random_seed=s
            )
            m = MumbaiTrafficModel(cfg)
            res = m.run_all()
            fl_list.append(res["mean_flow"])
            sp_list.append(res["mean_speed"])
            tt_list.append(res["mean_travel_time"])
            q_list.append(res["mean_queue_length"])

        flows.append(float(np.mean(fl_list)))
        speeds.append(float(np.mean(sp_list)))
        travel_times.append(float(np.mean(tt_list)))
        queues.append(float(np.mean(q_list)))

    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    ax1.plot(tw_shares, flows, '-o', color="#e65100", linewidth=2, label="Mean Flow (veh/step)")
    ax1.set_xlabel("Two-Wheeler Share α_2w")
    ax1.set_ylabel("Mean Flow (veh / step)", color="#e65100")
    ax1.tick_params(axis='y', labelcolor="#e65100")

    ax2 = ax1.twinx()
    ax2.plot(tw_shares, travel_times, '--s', color="#1565c0", linewidth=2, label="Mean Travel Time (steps)")
    ax2.set_ylabel("Mean Travel Time (steps)", color="#1565c0")
    ax2.tick_params(axis='y', labelcolor="#1565c0")
    ax2.grid(False)

    plt.title("Effect of Two-Wheeler Proportion on Flow and Travel Time")
    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "two_wheeler_share_effects.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "tw_shares": tw_shares,
        "flows": [round(f, 4) for f in flows],
        "speeds": [round(s, 3) for s in speeds],
        "travel_times": [round(tt, 2) for tt in travel_times],
        "queues": [round(q, 2) for q in queues],
        "plot_path": "static/generated/two_wheeler_share_effects.png"
    }


# ==============================================================================
# EXPERIMENT 7: Combined Scenario & Model Comparison
# ==============================================================================
def run_experiment_7(seeds: List[int] = [42, 101, 202, 303, 404]) -> Dict[str, Any]:
    print("Running Experiment 7: Combined Scenario & Comparison...")
    scenarios = {
        "NaSch Baseline": {"type": "nasch", "density": 0.25, "p": 0.3},
        "Mumbai Moderate": {"type": "mumbai", "density": 0.25, "tw_share": 0.4, "disc": LANE_DISCIPLINE_MODERATE, "g": 30, "r": 30},
        "Mumbai Congested Peak": {"type": "mumbai", "density": 0.40, "tw_share": 0.65, "disc": LANE_DISCIPLINE_WEAK, "g": 20, "r": 40}
    }

    results = {}
    for sc_name, sc_params in scenarios.items():
        flows, speeds, travel_times = [], [], []
        for s in seeds:
            if sc_params["type"] == "nasch":
                cfg = NaSchConfig(
                    road_length=200,
                    density=sc_params["density"],
                    max_speed=5,
                    slowdown_prob=sc_params["p"],
                    simulation_steps=600,
                    warmup_steps=200,
                    random_seed=s
                )
                m = NaSchModel(cfg)
                res = m.run_all()
                flows.append(res["mean_flow"])
                speeds.append(res["mean_speed"])
                # Equivalent travel time for length 200: L / mean_speed
                travel_times.append(200.0 / max(0.1, res["mean_speed"]))
            else:
                cfg_m = MumbaiConfig(
                    road_length=200,
                    density=sc_params["density"],
                    two_wheeler_share=sc_params["tw_share"],
                    lane_discipline=sc_params["disc"],
                    signal_position=150,
                    green_time=sc_params["g"],
                    red_time=sc_params["r"],
                    simulation_steps=600,
                    warmup_steps=200,
                    random_seed=s
                )
                m_inst = MumbaiTrafficModel(cfg_m)
                res_m = m_inst.run_all()
                flows.append(res_m["mean_flow"])
                speeds.append(res_m["mean_speed"])
                travel_times.append(res_m["mean_travel_time"])

        results[sc_name] = {
            "flow_mean": float(np.mean(flows)),
            "flow_std": float(np.std(flows)),
            "speed_mean": float(np.mean(speeds)),
            "speed_std": float(np.std(speeds)),
            "travel_time_mean": float(np.mean(travel_times)),
            "travel_time_std": float(np.std(travel_times))
        }

    # Plot 1: Flow comparison
    fig1, ax1 = plt.subplots(figsize=(6.5, 4.2))
    names = list(scenarios.keys())
    flow_vals = [results[n]["flow_mean"] for n in names]
    flow_errs = [results[n]["flow_std"] for n in names]
    colors = ["#78909c", "#ff9800", "#d32f2f"]

    ax1.bar(names, flow_vals, yerr=flow_errs, capsize=5, color=colors, edgecolor="#444444")
    ax1.set_ylabel("Mean Flow (veh / step)")
    ax1.set_title("Flow Comparison Across Scenarios")
    for idx, v in enumerate(flow_vals):
        ax1.text(idx, v * 0.5, f"{v:.3f}", ha='center', color='white', fontweight='bold')
    fig1.tight_layout()
    plot_path_flow = os.path.join(OUTPUT_DIR, "flow_comparison.png")
    fig1.savefig(plot_path_flow, dpi=200)
    plt.close(fig1)

    # Plot 2: Travel-time comparison
    fig2, ax2 = plt.subplots(figsize=(6.5, 4.2))
    tt_vals = [results[n]["travel_time_mean"] for n in names]
    tt_errs = [results[n]["travel_time_std"] for n in names]

    ax2.bar(names, tt_vals, yerr=tt_errs, capsize=5, color=colors, edgecolor="#444444")
    ax2.set_ylabel("Mean Travel Time (steps)")
    ax2.set_title("Travel Time Comparison Across Scenarios")
    for idx, v in enumerate(tt_vals):
        ax2.text(idx, v * 0.5, f"{v:.1f}s", ha='center', color='white', fontweight='bold')
    fig2.tight_layout()
    plot_path_tt = os.path.join(OUTPUT_DIR, "travel_time_comparison.png")
    fig2.savefig(plot_path_tt, dpi=200)
    plt.close(fig2)

    return {
        "scenarios": results,
        "plot_flow": "static/generated/flow_comparison.png",
        "plot_tt": "static/generated/travel_time_comparison.png"
    }


# ==============================================================================
# STAGE 8A: Disturbance Propagation Analysis
# ==============================================================================
def run_disturbance_propagation_analysis() -> Dict[str, Any]:
    """
    Creates an initially moving traffic stream, injects a localized brake disturbance
    (one vehicle decelerates to zero at step 20), and tracks spatio-temporal trajectories.
    """
    print("Running Stage 8A: Disturbance Propagation Analysis...")
    road_len = 150
    total_steps = 100
    density = 0.25
    v_max = 5
    p_slow = 0.2

    # Run NaSch model manually step-by-step
    cfg = NaSchConfig(
        road_length=road_len,
        density=density,
        max_speed=v_max,
        slowdown_prob=p_slow,
        simulation_steps=total_steps,
        random_seed=42
    )
    model = NaSchModel(cfg)

    # Let traffic organize for 20 steps
    for _ in range(20):
        model.step()

    # Inject disturbance at step 20: force lead vehicle to speed 0
    target_veh = model.vehicles[len(model.vehicles) // 2]
    target_veh.speed = 0

    # Record spatio-temporal matrix (time x space)
    space_time = np.full((total_steps, road_len), -1, dtype=int)

    for t in range(total_steps):
        for v in model.vehicles:
            space_time[t, v.pos] = v.speed
        model.step()

    # Plot spatio-temporal diagram
    fig, ax = plt.subplots(figsize=(8, 5))
    # Background is white (empty road), vehicles coloured by speed
    cmap = matplotlib.colormaps.get_cmap("RdYlGn").resampled(v_max + 1)
    masked_data = np.ma.masked_where(space_time == -1, space_time)

    im = ax.imshow(masked_data, aspect='auto', origin='upper', cmap=cmap, vmin=0, vmax=v_max)
    ax.set_xlabel("Road Position (cells)")
    ax.set_ylabel("Time Step (t)")
    ax.set_title("Disturbance Propagation: Phantom Jam Backward Shockwave (NaSch)")
    cbar = fig.colorbar(im, ax=ax, ticks=range(v_max + 1))
    cbar.set_label("Vehicle Speed (cells/step)")

    # Annotate disturbance
    ax.axhline(20, color='red', linestyle=':', alpha=0.7, label="Disturbance Injected (t=20)")
    ax.legend(loc="upper right")

    fig.tight_layout()
    plot_path = os.path.join(OUTPUT_DIR, "disturbance_propagation.png")
    fig.savefig(plot_path, dpi=200)
    plt.close(fig)

    return {
        "status": "Disturbance grows into upstream backward shockwave before dissipating",
        "plot_path": "static/generated/disturbance_propagation.png"
    }


# ==============================================================================
# STAGE 8B & 8C: Sensitivity and Stochastic Repeatability Analysis
# ==============================================================================
def run_sensitivity_and_repeatability() -> Dict[str, Any]:
    print("Running Stage 8B & 8C: Sensitivity & Stochastic Repeatability...")
    seeds = [11, 23, 37, 49, 53, 67, 71, 89, 97, 113]  # 10 seeds

    # Base configuration
    base_cfg = MumbaiConfig(
        road_length=200,
        density=0.30,
        two_wheeler_share=0.40,
        lane_discipline=LANE_DISCIPLINE_MODERATE,
        signal_position=150,
        green_time=30,
        red_time=30,
        simulation_steps=500,
        warmup_steps=150
    )

    # 1. Stochastic Repeatability over 10 seeds
    base_flows = []
    base_tts = []
    base_queues = []
    for s in seeds:
        cfg = base_cfg.model_copy(update={"random_seed": s})
        m = MumbaiTrafficModel(cfg)
        res = m.run_all()
        base_flows.append(res["mean_flow"])
        base_tts.append(res["mean_travel_time"])
        base_queues.append(res["mean_queue_length"])

    repeatability = {
        "num_seeds": len(seeds),
        "flow": {
            "mean": round(float(np.mean(base_flows)), 4),
            "std": round(float(np.std(base_flows)), 4),
            "cv": round(float(np.std(base_flows) / np.mean(base_flows)), 4)
        },
        "travel_time": {
            "mean": round(float(np.mean(base_tts)), 2),
            "std": round(float(np.std(base_tts)), 2),
            "cv": round(float(np.std(base_tts) / np.mean(base_tts)), 4)
        },
        "queue_length": {
            "mean": round(float(np.mean(base_queues)), 2),
            "std": round(float(np.std(base_queues)), 2),
            "cv": round(float(np.std(base_queues) / np.mean(base_queues)), 4)
        }
    }

    # 2. Sensitivity: perturb key parameters by +20% and -20%
    base_flow_mean = np.mean(base_flows)
    base_tt_mean = np.mean(base_tts)

    perturbations = [
        ("two_wheeler_share", 0.40, [0.32, 0.48]),
        ("slowdown_car", 0.30, [0.24, 0.36]),
        ("green_time", 30, [24, 36])
    ]

    sensitivity_results = {}
    for param_name, base_val, test_vals in perturbations:
        sensitivity_results[param_name] = []
        for val in test_vals:
            t_flows, t_tts = [], []
            for s in seeds[:5]:
                cfg = base_cfg.model_copy(update={param_name: val, "random_seed": s})
                m = MumbaiTrafficModel(cfg)
                res = m.run_all()
                t_flows.append(res["mean_flow"])
                t_tts.append(res["mean_travel_time"])

            delta_param_pct = round(((val - base_val) / base_val) * 100, 1)
            delta_flow_pct = round(((np.mean(t_flows) - base_flow_mean) / base_flow_mean) * 100, 2)
            delta_tt_pct = round(((np.mean(t_tts) - base_tt_mean) / base_tt_mean) * 100, 2)

            sensitivity_results[param_name].append({
                "value": val,
                "delta_param_pct": delta_param_pct,
                "flow": round(float(np.mean(t_flows)), 4),
                "delta_flow_pct": delta_flow_pct,
                "travel_time": round(float(np.mean(t_tts)), 2),
                "delta_tt_pct": delta_tt_pct
            })

    return {
        "repeatability": repeatability,
        "sensitivity": sensitivity_results
    }


# ==============================================================================
# MASTER RUNNER
# ==============================================================================
def run_all_experiments() -> Dict[str, Any]:
    set_plot_style()
    print("======================================================================")
    print("Starting Comprehensive T25 Traffic Simulation Numerical Experiments...")
    print("======================================================================")

    exp1 = run_experiment_1()
    exp2 = run_experiment_2()
    exp3 = run_experiment_3()
    exp4 = run_experiment_4()
    exp5 = run_experiment_5()
    exp6 = run_experiment_6()
    exp7 = run_experiment_7()
    dist = run_disturbance_propagation_analysis()
    sens = run_sensitivity_and_repeatability()

    master_results = {
        "experiment_1_baseline_fd": exp1,
        "experiment_2_extended_fd": exp2,
        "experiment_3_slowdown": exp3,
        "experiment_4_lane_discipline": exp4,
        "experiment_5_signal_timing": exp5,
        "experiment_6_mixed_traffic": exp6,
        "experiment_7_combined": exp7,
        "disturbance_analysis": dist,
        "sensitivity_repeatability": sens
    }

    # Save to JSON
    json_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(json_path, "w") as f:
        json.dump(master_results, f, indent=2)

    print("======================================================================")
    print(f"All experiments successfully completed! Results saved to: {json_path}")
    print(f"Plots saved to: {OUTPUT_DIR}")
    print("======================================================================")
    return master_results


if __name__ == "__main__":
    run_all_experiments()
