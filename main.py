"""
main.py - FastAPI application for T25 Traffic Simulation
(Nagel-Schreckenberg Baseline & Improved Mumbai Arterial Model)
"""

import os
import json
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from simulation import (
    NaSchModel, NaSchConfig,
    MumbaiTrafficModel, MumbaiConfig,
    LANE_DISCIPLINE_STRONG, LANE_DISCIPLINE_MODERATE, LANE_DISCIPLINE_WEAK
)
import experiments

app = FastAPI(
    title="T25: Mumbai Traffic Cellular Automaton Simulation",
    description="Cellular-Automaton Traffic Simulation of a Congested Mumbai Arterial Road vs NaSch Baseline",
    version="1.0.0"
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
GENERATED_DIR = os.path.join(STATIC_DIR, "generated")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# In-memory interactive session store
interactive_sessions: Dict[str, Any] = {}


class SimulationRequest(BaseModel):
    model_type: str = Field(default="mumbai", description="'nasch' or 'mumbai'")
    road_length: int = Field(default=200, ge=20, le=1000)
    density: float = Field(default=0.25, ge=0.01, le=0.95)
    max_speed_car: int = Field(default=4, ge=1, le=8)
    max_speed_two_wheeler: int = Field(default=5, ge=1, le=8)
    slowdown_prob: float = Field(default=0.3, ge=0.0, le=1.0)
    slowdown_car: float = Field(default=0.3, ge=0.0, le=1.0)
    slowdown_two_wheeler: float = Field(default=0.15, ge=0.0, le=1.0)
    two_wheeler_share: float = Field(default=0.4, ge=0.0, le=1.0)
    lane_discipline: str = Field(default=LANE_DISCIPLINE_MODERATE)
    signal_position: int = Field(default=150, ge=10, le=990)
    green_time: int = Field(default=30, ge=5, le=300)
    red_time: int = Field(default=30, ge=5, le=300)
    simulation_steps: int = Field(default=400, ge=20, le=3000)
    warmup_steps: int = Field(default=100, ge=0, le=1000)
    random_seed: Optional[int] = Field(default=42)
    is_circular: bool = Field(default=False)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Renders the main simulation and experiment dashboard."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/simulate/run")
async def run_simulation(req: SimulationRequest):
    """Runs a complete batch simulation and returns steady-state summary metrics."""
    try:
        if req.model_type == "nasch":
            cfg = NaSchConfig(
                road_length=req.road_length,
                density=req.density,
                max_speed=req.max_speed_car,
                slowdown_prob=req.slowdown_prob,
                simulation_steps=req.simulation_steps,
                warmup_steps=req.warmup_steps,
                random_seed=req.random_seed
            )
            model = NaSchModel(cfg)
            results = model.run_all()
            return {"status": "success", "data": results}
        elif req.model_type == "mumbai":
            cfg = MumbaiConfig(
                road_length=req.road_length,
                density=req.density,
                max_speed_car=req.max_speed_car,
                max_speed_two_wheeler=req.max_speed_two_wheeler,
                slowdown_car=req.slowdown_car,
                slowdown_two_wheeler=req.slowdown_two_wheeler,
                two_wheeler_share=req.two_wheeler_share,
                lane_discipline=req.lane_discipline,
                signal_position=min(req.signal_position, req.road_length - 5),
                green_time=req.green_time,
                red_time=req.red_time,
                simulation_steps=req.simulation_steps,
                warmup_steps=req.warmup_steps,
                random_seed=req.random_seed,
                is_circular=req.is_circular
            )
            model = MumbaiTrafficModel(cfg)
            results = model.run_all()
            return {"status": "success", "data": results}
        else:
            raise HTTPException(status_code=400, detail="Invalid model_type. Choose 'nasch' or 'mumbai'.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/simulate/interactive/init")
async def init_interactive(req: SimulationRequest):
    """Initializes an interactive simulation instance for step-by-step animation in the UI."""
    session_id = "default_session"
    if req.model_type == "nasch":
        cfg = NaSchConfig(
            road_length=req.road_length,
            density=req.density,
            max_speed=req.max_speed_car,
            slowdown_prob=req.slowdown_prob,
            simulation_steps=req.simulation_steps,
            warmup_steps=req.warmup_steps,
            random_seed=req.random_seed
        )
        model = NaSchModel(cfg)
        interactive_sessions[session_id] = {"model": model, "type": "nasch"}
        return {
            "status": "initialized",
            "model_type": "nasch",
            "road_length": model.road_length,
            "num_lanes": 1,
            "step": model.current_step,
            "vehicles": [v.to_dict() for v in model.vehicles],
            "signal_state": "none"
        }
    else:
        cfg = MumbaiConfig(
            road_length=req.road_length,
            density=req.density,
            max_speed_car=req.max_speed_car,
            max_speed_two_wheeler=req.max_speed_two_wheeler,
            slowdown_car=req.slowdown_car,
            slowdown_two_wheeler=req.slowdown_two_wheeler,
            two_wheeler_share=req.two_wheeler_share,
            lane_discipline=req.lane_discipline,
            signal_position=min(req.signal_position, req.road_length - 5),
            green_time=req.green_time,
            red_time=req.red_time,
            simulation_steps=req.simulation_steps,
            warmup_steps=req.warmup_steps,
            random_seed=req.random_seed,
            is_circular=req.is_circular
        )
        model = MumbaiTrafficModel(cfg)
        interactive_sessions[session_id] = {"model": model, "type": "mumbai"}
        return {
            "status": "initialized",
            "model_type": "mumbai",
            **model.get_state()
        }


@app.post("/api/simulate/interactive/step")
async def step_interactive():
    """Advances the current interactive simulation by one step."""
    session_id = "default_session"
    if session_id not in interactive_sessions:
        raise HTTPException(status_code=400, detail="Interactive session not initialized.")

    session = interactive_sessions[session_id]
    model = session["model"]
    model_type = session["type"]

    model.step()

    if model_type == "nasch":
        return {
            "step": model.current_step,
            "model_type": "nasch",
            "road_length": model.road_length,
            "num_lanes": 1,
            "vehicles": [v.to_dict() for v in model.vehicles],
            "signal_state": "none",
            "mean_speed": round(float(model.history_mean_speed[-1]), 2) if model.history_mean_speed else 0.0,
            "flow": round(float(model.history_flow[-1]), 4) if model.history_flow else 0.0,
            "completed_count": len(model.vehicles),
            "queue_length": 0
        }
    else:
        return {
            "model_type": "mumbai",
            **model.get_state()
        }


@app.get("/api/experiments/results")
async def get_experiment_results():
    """Returns the cached experimental numerical results."""
    results_path = os.path.join(GENERATED_DIR, "results.json")
    if not os.path.exists(results_path):
        # Run experiments if not yet executed
        res = experiments.run_all_experiments()
        return res
    with open(results_path, "r") as f:
        data = json.load(f)
    return data


@app.post("/api/experiments/run")
async def trigger_experiments():
    """Re-runs all numerical experiments and regenerates plots."""
    results = experiments.run_all_experiments()
    return {"status": "success", "results": results}


@app.get("/api/plots")
async def list_plots():
    """Lists all 9 verified experiment plots available for display."""
    plot_names = [
        ("baseline_fundamental_diagram.png", "Exp 1: Baseline NaSch Fundamental Diagram (Flow vs Density)"),
        ("extended_fundamental_diagram.png", "Exp 2: Extended Mumbai Arterial vs Circular Fundamental Diagram"),
        ("random_slowdown_effects.png", "Exp 3: Effects of Random Slowdown Probability (p)"),
        ("lane_discipline_effects.png", "Exp 4: Effects of Lane Discipline (Strong vs Moderate vs Weak)"),
        ("signal_timing_effects.png", "Exp 5: Effects of Signal Timing Splits (Green/Red Splits)"),
        ("two_wheeler_share_effects.png", "Exp 6: Effects of Two-Wheeler Share on Flow & Travel Time"),
        ("flow_comparison.png", "Exp 7: Flow Comparison Across Scenarios"),
        ("travel_time_comparison.png", "Exp 7: Travel Time Comparison Across Scenarios"),
        ("disturbance_propagation.png", "Stability: Disturbance Propagation & Shockwave Trajectories")
    ]
    return [
        {"filename": name, "title": title, "url": f"/static/generated/{name}"}
        for name, title in plot_names
    ]
