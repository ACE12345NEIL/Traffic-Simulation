# T25 — Cellular-Automaton Traffic Simulation of a Congested Mumbai Arterial Road

## 1. Project Overview

This project implements a stochastic Cellular Automaton (CA) traffic simulation comparing the classical single-lane freeway model of **Nagel & Schreckenberg (1992)** against an improved, multi-lane, heterogeneous model calibrated for urban arterial traffic in **Mumbai, India**.

### Research Questions
- How do **lane discipline**, **random slowdowns (dawdling)**, and **traffic signal timing** affect vehicle flow, travel times, and queue spillback on congested arterial corridors?
- Can a discrete cellular automaton capture the **empirical fundamental diagram** (flow vs. density) and reproduce real-world traffic phenomena such as **phantom traffic jams** and **arterial bottleneck shockwaves**?

---

## 2. Main Features

- **Baseline NaSch (1992) Engine**: Full synchronous implementation of the four original rules (Acceleration, Braking, Random Dawdling, Movement) on a circular lattice.
- **Improved Mumbai Mixed-Traffic Engine**:
  - **Heterogeneous Vehicles**: Cars (standard braking, moderate speed) and Two-Wheelers (high maneuverability, low dawdling).
  - **Multi-Lane Safe Lane Changing**: Incentive and safety criteria conditioned on **Lane Discipline** (Strong, Moderate, Weak).
  - **Signalized Arterial Queuing**: Real-time stop-line constraint with configurable Green/Red cycles, queue spillback, and travel-time measurement on an open road.
- **FastAPI Web Application**:
  - Interactive browser UI with step-by-step road cell visualization.
  - Distinct color coding: Cars (Dark Navy `#2b3a4a`), Two-Wheelers (Bright Orange `#ff6600`), Traffic Signal (Red/Green light indicator).
  - Playback controls: Play, Pause, Single-Step, Reset, and Animation Speed.
  - Real-time display of Steady-State Flow, Mean Speed, Mean Travel Time, and Queue Lengths.
- **Comprehensive Numerical Experiments (1–7)**:
  - Automated multi-seed runs with error bounds and publication-quality plots.
- **Stability & Sensitivity Analysis**:
  - Spatio-temporal disturbance propagation (backward shockwave analysis).
  - Parameter sensitivity ($\pm 20\%$ perturbation) and 10-seed stochastic repeatability.

---

## 3. Project Structure

```text
T25-Traffic-Simulation/
├── main.py                  # FastAPI server and HTTP API endpoints
├── simulation.py            # NaSchModel and MumbaiTrafficModel CA engines
├── experiments.py           # Numerical experiments runner and plot generator
├── test_models.py           # Unit tests for CA rules, safety, and non-overlap
├── requirements.txt         # Minimal Python dependencies
├── README.md                # Project documentation and setup guide
├── REPORT.md                # Full 33-section scientific research report
├── templates/
│   └── index.html           # Responsive web interface template
└── static/
    ├── style.css            # Stylesheet (white background, dark grey text, orange accents)
    ├── app.js               # Frontend animation and REST client
    └── generated/           # Experiment result tables, master JSON, and 9 plots
```

---

## 4. Requirements & Installation (Windows)

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- PowerShell or Command Prompt

### Step 1: Clone or navigate to the workspace directory
```powershell
cd "c:\Users\Neil Shinde\Desktop\PROJECTS\MnS CS"
```

### Step 2: (Optional) Create and activate a virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies
```powershell
pip install -r requirements.txt
```

---

## 5. Execution Instructions

### A. Run Unit Tests
Verify model physics, non-overlap, safe lane changing, and signal compliance:
```powershell
python test_models.py
```

### B. Run Numerical Experiments & Generate All 9 Plots
Execute the automated experimental suite (saves all plots and numerical results to `static/generated/`):
```powershell
python experiments.py
```

### C. Launch the FastAPI Web Interface
Start the Uvicorn web server:
```powershell
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### D. Open in Browser
Navigate to:
```
http://127.0.0.1:8000
```

---

## 6. Model Modes & Simulation Controls

The web interface provides an intuitive control panel:

| Control | Range | Description |
|---|---|---|
| **Model Architecture** | `NaSch` / `Mumbai` | Selects between the baseline 1992 model or the improved Mumbai model. |
| **Traffic Density ($\rho$)** | `0.02 – 0.90` | Fraction of road occupied or inflow arrival demand. |
| **Road Length ($L$)** | `50 – 400 cells` | Total segment length (default 200 cells; 1 cell $\approx 5\text{ m}$). |
| **Two-Wheeler Share ($\alpha_{2w}$)** | `0.0 – 1.0` | Proportion of two-wheelers in the vehicle mix (Mumbai mode). |
| **Lane Discipline** | `Strong` / `Moderate` / `Weak` | Controls lane-changing aggressiveness and filtering tendency. |
| **Signal Stop Line** | `30 – 380 cells` | Cell index of the signalized intersection stop line. |
| **Green / Red Duration** | `5 – 120 steps` | Duration of green and red signal phases (1 step $\approx 1\text{ s}$). |
| **Random Seed** | Integer | Ensures deterministic reproducibility of stochastic runs. |

---

## 7. Numerical Experiments Summary

| Experiment | Focus | Key Finding |
|---|---|---|
| **Exp 1: Baseline Fundamental Diagram** | Flow vs. Density for NaSch | Reproduces peak flow $J_{\max} \approx 0.50$ at $\rho_c \approx 0.12$; clear transition from free flow to congested regime. |
| **Exp 2: Extended Fundamental Diagram** | Open arterial with signal vs. circular | Traffic signal introduces structural capacity bottleneck, reducing throughput and inducing upstream queue spillback. |
| **Exp 3: Random Slowdowns ($p$)** | Dawdling parameter sweep ($0.05 - 0.60$) | Higher dawdling drastically degrades capacity; speed drops by over $65\%$ in congested regimes. |
| **Exp 4: Lane Discipline** | Strong vs. Moderate vs. Weak | Weak discipline increases flow marginally at moderate density via opportunistic gap filling, but induces friction at high density. |
| **Exp 5: Signal Timing** | Green/Red phase splits ($15G/45R$ to $45G/15R$) | Travel time decreases monotonically as green ratio increases; queues drop significantly. |
| **Exp 6: Mixed Traffic** | Two-wheeler proportion ($0\% - 100\%$) | Higher two-wheeler share reduces space occupancy and improves flow due to agility, but travel time is bound by signal delays. |
| **Exp 7: Combined Scenario** | Baseline vs. Moderate vs. Congested Peak | Compares baseline freeway with realistic congested arterial exhibiting $15\times$ longer travel times under heavy queuing. |

---

## 8. Research Report Location

The comprehensive, 33-section academic research report is located at:
- [`REPORT.md`](REPORT.md)

It includes complete mathematical formulations, derivation of update rules, parameter calibration tables, assumption documentation, stability proofs via disturbance propagation diagrams, and critical analysis of model limitations.
