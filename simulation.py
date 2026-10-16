"""
simulation.py - Cellular Automata Traffic Models

Implements:
1. NaSchModel: Original single-lane Nagel-Schreckenberg (1992) model with periodic boundaries.
2. MumbaiTrafficModel: Extended multi-lane, heterogeneous (cars + two-wheelers),
   lane discipline, and signal-controlled open-road arterial model.
"""

from typing import List, Dict, Tuple, Optional, Any
import numpy as np
from pydantic import BaseModel, Field


# Vehicle Type Constants
TYPE_CAR = 0
TYPE_TWO_WHEELER = 1

# Lane Discipline Mode Constants
LANE_DISCIPLINE_STRONG = "strong"
LANE_DISCIPLINE_MODERATE = "moderate"
LANE_DISCIPLINE_WEAK = "weak"


class Vehicle:
    """Represents an individual vehicle in the simulation."""
    def __init__(
        self,
        veh_id: int,
        veh_type: int,
        pos: int,
        lane: int = 0,
        speed: int = 0,
        max_speed: int = 5,
        slowdown_prob: float = 0.3,
        entry_step: int = 0
    ):
        self.veh_id = veh_id
        self.veh_type = veh_type  # TYPE_CAR or TYPE_TWO_WHEELER
        self.pos = pos            # 0 to road_length - 1
        self.lane = lane          # 0 or 1
        self.speed = speed
        self.max_speed = max_speed
        self.slowdown_prob = slowdown_prob
        self.entry_step = entry_step
        self.exit_step: Optional[int] = None
        self.travel_time: Optional[int] = None
        self.waited_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.veh_id,
            "type": "car" if self.veh_type == TYPE_CAR else "two_wheeler",
            "pos": self.pos,
            "lane": self.lane,
            "speed": self.speed,
            "max_speed": self.max_speed,
            "slowdown_prob": self.slowdown_prob,
        }


class NaSchConfig(BaseModel):
    """Configuration for the baseline single-lane Nagel-Schreckenberg model."""
    road_length: int = Field(default=200, ge=20, le=2000, description="Number of discrete cells (L)")
    density: float = Field(default=0.2, ge=0.01, le=0.99, description="Initial vehicle density (rho)")
    max_speed: int = Field(default=5, ge=1, le=10, description="Max speed in cells/step (v_max)")
    slowdown_prob: float = Field(default=0.3, ge=0.0, le=1.0, description="Random braking probability (p)")
    simulation_steps: int = Field(default=500, ge=10, le=5000, description="Total simulation steps")
    warmup_steps: int = Field(default=100, ge=0, le=2000, description="Steps excluded from steady-state stats")
    random_seed: Optional[int] = Field(default=42, description="Random seed for reproducibility")


class MumbaiConfig(BaseModel):
    """Configuration for the improved Mumbai arterial traffic model."""
    road_length: int = Field(default=200, ge=20, le=2000, description="Segment length in cells")
    density: float = Field(default=0.25, ge=0.01, le=0.99, description="Inflow demand density")
    max_speed_car: int = Field(default=4, ge=1, le=8, description="Car max speed (cells/step)")
    max_speed_two_wheeler: int = Field(default=5, ge=1, le=8, description="Two-wheeler max speed (cells/step)")
    slowdown_car: float = Field(default=0.3, ge=0.0, le=1.0, description="Car dawdling probability")
    slowdown_two_wheeler: float = Field(default=0.15, ge=0.0, le=1.0, description="Two-wheeler dawdling probability")
    two_wheeler_share: float = Field(default=0.4, ge=0.0, le=1.0, description="Fraction of two-wheelers")
    lane_discipline: str = Field(default=LANE_DISCIPLINE_MODERATE, description="'strong', 'moderate', or 'weak'")
    signal_position: int = Field(default=150, ge=5, le=1990, description="Stop line cell index")
    green_time: int = Field(default=30, ge=5, le=300, description="Green light duration in steps")
    red_time: int = Field(default=30, ge=5, le=300, description="Red light duration in steps")
    simulation_steps: int = Field(default=500, ge=10, le=5000, description="Total simulation steps")
    warmup_steps: int = Field(default=100, ge=0, le=2000, description="Warm-up steps before measurement")
    random_seed: Optional[int] = Field(default=42, description="Random seed")
    is_circular: bool = Field(default=False, description="Whether to use circular boundary (for pure FD tests)")


class NaSchModel:
    """
    Original Single-Lane Nagel-Schreckenberg (1992) Cellular Automaton Model.
    Periodic boundary conditions (circular road).
    Four synchronous update rules:
      1. Acceleration: v = min(v + 1, v_max)
      2. Braking: v = min(v, gap)
      3. Randomisation: if v > 0, v = v - 1 with prob p
      4. Movement: x = (x + v) % L
    """
    def __init__(self, config: NaSchConfig):
        self.config = config
        self.road_length = config.road_length
        self.v_max = config.max_speed
        self.p = config.slowdown_prob
        self.steps = config.simulation_steps
        self.warmup = config.warmup_steps
        self.rng = np.random.RandomState(config.random_seed)

        # State: array of size road_length with -1 for empty, or velocity >= 0
        self.current_step = 0
        self.vehicles: List[Vehicle] = []
        self._init_road()

        # Metrics history
        self.history_mean_speed: List[float] = []
        self.history_flow: List[float] = []
        self.history_density: List[float] = []

    def _init_road(self):
        """Initializes vehicles uniformly on the circular road to match target density."""
        num_vehicles = int(round(self.config.density * self.road_length))
        num_vehicles = max(1, min(num_vehicles, self.road_length - 1))
        
        # Select unique random positions
        chosen_positions = self.rng.choice(self.road_length, size=num_vehicles, replace=False)
        chosen_positions.sort()

        self.vehicles = []
        for idx, pos in enumerate(chosen_positions):
            initial_speed = self.rng.randint(0, self.v_max + 1)
            v = Vehicle(
                veh_id=idx,
                veh_type=TYPE_CAR,
                pos=int(pos),
                lane=0,
                speed=initial_speed,
                max_speed=self.v_max,
                slowdown_prob=self.p
            )
            self.vehicles.append(v)

    def get_gap(self, veh_idx: int) -> int:
        """Computes the number of empty cells ahead of the vehicle on a circular road."""
        curr_pos = self.vehicles[veh_idx].pos
        next_idx = (veh_idx + 1) % len(self.vehicles)
        next_pos = self.vehicles[next_idx].pos

        if next_pos > curr_pos:
            return next_pos - curr_pos - 1
        else:
            # Wraps around the circular boundary
            return (self.road_length - curr_pos) + next_pos - 1

    def step(self):
        """Executes one time step with synchronous updates."""
        if not self.vehicles:
            return

        n = len(self.vehicles)
        new_speeds = np.zeros(n, dtype=int)

        # Rule 1, 2, 3: Acceleration, Braking, Randomisation
        for i in range(n):
            v = self.vehicles[i].speed
            # 1. Acceleration
            v = min(v + 1, self.v_max)
            
            # 2. Braking
            gap = self.get_gap(i)
            v = min(v, gap)
            
            # 3. Randomisation
            if v > 0 and self.rng.rand() < self.p:
                v -= 1

            new_speeds[i] = v

        # Rule 4: Movement (Synchronous)
        for i in range(n):
            self.vehicles[i].speed = int(new_speeds[i])
            self.vehicles[i].pos = (self.vehicles[i].pos + self.vehicles[i].speed) % self.road_length

        self.current_step += 1

        # Metrics for this step
        speeds = [v.speed for v in self.vehicles]
        mean_speed = float(np.mean(speeds)) if speeds else 0.0
        density = len(self.vehicles) / self.road_length
        flow = density * mean_speed  # vehicles per cell per time step

        self.history_mean_speed.append(mean_speed)
        self.history_density.append(density)
        self.history_flow.append(flow)

    def run_all(self) -> Dict[str, Any]:
        """Runs the simulation for all configured steps and calculates summary stats."""
        while self.current_step < self.steps:
            self.step()

        # Steady-state results (after warmup)
        if self.warmup < len(self.history_flow):
            ss_flow = float(np.mean(self.history_flow[self.warmup:]))
            ss_speed = float(np.mean(self.history_mean_speed[self.warmup:]))
            ss_density = float(np.mean(self.history_density[self.warmup:]))
        else:
            ss_flow = float(np.mean(self.history_flow)) if self.history_flow else 0.0
            ss_speed = float(np.mean(self.history_mean_speed)) if self.history_mean_speed else 0.0
            ss_density = float(np.mean(self.history_density)) if self.history_density else 0.0

        return {
            "model": "NaSch_Original",
            "road_length": self.road_length,
            "density": ss_density,
            "vehicle_count": len(self.vehicles),
            "mean_flow": ss_flow,
            "mean_speed": ss_speed,
            "total_steps": self.current_step,
            "warmup_steps": self.warmup,
        }

    def get_road_state(self) -> List[int]:
        """Returns array of length L with vehicle speed, or -1 if empty."""
        grid = [-1] * self.road_length
        for v in self.vehicles:
            grid[v.pos] = v.speed
        return grid


class MumbaiTrafficModel:
    """
    Improved Mumbai Arterial Road Traffic Model.
    Features:
      1. Heterogeneous vehicles: Cars (large, moderate speed, standard braking)
         and Two-Wheelers (agile, faster acceleration, lower dawdling).
      2. Multi-lane (2 lanes) with safe lane changing & Lane Discipline parameter
         (strong, moderate, weak).
      3. Signal-controlled traffic: stop line at configurable position with
         red/green cycles, queue tracking.
      4. Open-road finite arterial configuration (default) with inflow / outflow,
         or circular road mode for pure fundamental diagram comparison.
    """
    def __init__(self, config: MumbaiConfig):
        self.config = config
        self.road_length = config.road_length
        self.num_lanes = 2
        self.steps = config.simulation_steps
        self.warmup = config.warmup_steps
        self.signal_pos = config.signal_position
        self.green_time = config.green_time
        self.red_time = config.red_time
        self.cycle_time = self.green_time + self.red_time
        self.lane_discipline = config.lane_discipline
        self.two_wheeler_share = config.two_wheeler_share
        self.is_circular = config.is_circular
        self.rng = np.random.RandomState(config.random_seed)

        self.current_step = 0
        self.next_veh_id = 0
        self.vehicles: List[Vehicle] = []
        self.completed_trips: List[Vehicle] = []

        # Lane change probabilities based on lane discipline
        # Under weak discipline (Mumbai weaving/filtering), lane changing is very aggressive
        if self.lane_discipline == LANE_DISCIPLINE_STRONG:
            self.p_change_car = 0.20
            self.p_change_tw = 0.35
        elif self.lane_discipline == LANE_DISCIPLINE_WEAK:
            self.p_change_car = 0.80
            self.p_change_tw = 0.95
        else:  # MODERATE
            self.p_change_car = 0.50
            self.p_change_tw = 0.65

        # Initialize road
        self._init_road()

        # Step metrics
        self.history_mean_speed: List[float] = []
        self.history_flow: List[float] = []
        self.history_density: List[float] = []
        self.history_queue_length: List[int] = []
        self.history_signal_state: List[str] = []
        self.detector_crossings: int = 0  # Count of vehicles crossing the signal stop line

    def is_green(self, step: Optional[int] = None) -> bool:
        """Returns True if traffic signal is green at the given step."""
        t = self.current_step if step is None else step
        return (t % self.cycle_time) < self.green_time

    def _init_road(self):
        """Initializes vehicles on the 2 lanes."""
        self.vehicles = []
        self.completed_trips = []
        self.next_veh_id = 0

        if self.is_circular:
            # Populate both lanes according to target density
            total_cells = self.road_length * self.num_lanes
            num_vehicles = int(round(self.config.density * total_cells))
            num_vehicles = max(1, min(num_vehicles, total_cells - 2))

            all_cells = [(l, p) for l in range(self.num_lanes) for p in range(self.road_length)]
            chosen_indices = self.rng.choice(len(all_cells), size=num_vehicles, replace=False)
            
            for idx in chosen_indices:
                lane, pos = all_cells[idx]
                is_tw = self.rng.rand() < self.two_wheeler_share
                v_type = TYPE_TWO_WHEELER if is_tw else TYPE_CAR
                v_max = self.config.max_speed_two_wheeler if is_tw else self.config.max_speed_car
                p_slow = self.config.slowdown_two_wheeler if is_tw else self.config.slowdown_car
                speed = self.rng.randint(0, v_max + 1)
                
                veh = Vehicle(
                    veh_id=self.next_veh_id,
                    veh_type=v_type,
                    pos=pos,
                    lane=lane,
                    speed=speed,
                    max_speed=v_max,
                    slowdown_prob=p_slow,
                    entry_step=0
                )
                self.next_veh_id += 1
                self.vehicles.append(veh)
        else:
            # Finite road: start with an initial warm spread of vehicles upstream
            init_count = int(self.config.density * self.road_length * self.num_lanes * 0.5)
            cells_pool = [(l, p) for l in range(self.num_lanes) for p in range(0, min(self.road_length, self.signal_pos))]
            if cells_pool and init_count > 0:
                chosen = self.rng.choice(len(cells_pool), size=min(init_count, len(cells_pool)), replace=False)
                for idx in chosen:
                    lane, pos = cells_pool[idx]
                    is_tw = self.rng.rand() < self.two_wheeler_share
                    v_type = TYPE_TWO_WHEELER if is_tw else TYPE_CAR
                    v_max = self.config.max_speed_two_wheeler if is_tw else self.config.max_speed_car
                    p_slow = self.config.slowdown_two_wheeler if is_tw else self.config.slowdown_car
                    veh = Vehicle(
                        veh_id=self.next_veh_id,
                        veh_type=v_type,
                        pos=pos,
                        lane=lane,
                        speed=self.rng.randint(0, 3),
                        max_speed=v_max,
                        slowdown_prob=p_slow,
                        entry_step=0
                    )
                    self.next_veh_id += 1
                    self.vehicles.append(veh)

    def _get_grid_maps(self) -> Tuple[Dict[Tuple[int, int], Vehicle], Dict[int, List[Vehicle]]]:
        """Returns spatial lookup map and per-lane sorted vehicle lists."""
        cell_map: Dict[Tuple[int, int], Vehicle] = {}
        lane_map: Dict[int, List[Vehicle]] = {0: [], 1: []}
        
        for v in self.vehicles:
            cell_map[(v.lane, v.pos)] = v
            lane_map[v.lane].append(v)
            
        for l in range(self.num_lanes):
            lane_map[l].sort(key=lambda veh: veh.pos)
            
        return cell_map, lane_map

    def _get_forward_gap(self, veh: Vehicle, lane: int, lane_vehicles: List[Vehicle]) -> int:
        """Calculates distance in empty cells to the next vehicle ahead in the given lane."""
        pos = veh.pos
        if not lane_vehicles:
            return self.road_length

        ahead = [v for v in lane_vehicles if v.pos > pos]
        if ahead:
            return ahead[0].pos - pos - 1
        elif self.is_circular:
            # Wrap around circular road
            behind = [v for v in lane_vehicles if v.pos <= pos and v.veh_id != veh.veh_id]
            if behind:
                return (self.road_length - pos) + behind[0].pos - 1
            else:
                return self.road_length - 1
        else:
            # Open road: no vehicle ahead, unobstructed exit
            return self.road_length

    def _get_backward_gap(self, veh: Vehicle, target_lane: int, target_lane_vehicles: List[Vehicle]) -> int:
        """Calculates distance in empty cells to the vehicle behind in target lane."""
        pos = veh.pos
        behind = [v for v in target_lane_vehicles if v.pos < pos]
        if behind:
            return pos - behind[-1].pos - 1
        elif self.is_circular:
            ahead = [v for v in target_lane_vehicles if v.pos >= pos and v.veh_id != veh.veh_id]
            if ahead:
                return pos + (self.road_length - ahead[-1].pos) - 1
            else:
                return self.road_length - 1
        else:
            return self.road_length  # Clear backward headway to entry on open road

    def _lane_changing_phase(self):
        """
        Executes safe lane changing rules:
        1. Incentive: hindered in current lane, better gap in target lane.
        2. Safety: target cell free, adequate back-gap so follower doesn't crash.
        3. Lane discipline stochastic acceptance.
        4. No dual-assignment collision.
        """
        cell_map, lane_map = self._get_grid_maps()
        intended_changes: List[Tuple[Vehicle, int]] = []
        claimed_cells = set(cell_map.keys())

        # Sort vehicles from front to back to maintain deterministic priority
        sorted_vehs = sorted(self.vehicles, key=lambda v: -v.pos)

        for veh in sorted_vehs:
            curr_lane = veh.lane
            target_lane = 1 - curr_lane
            pos = veh.pos

            target_cell = (target_lane, pos)
            # Rule 1: Target cell must be vacant
            if target_cell in claimed_cells:
                continue

            curr_gap = self._get_forward_gap(veh, curr_lane, lane_map[curr_lane])
            target_gap_ahead = self._get_forward_gap(veh, target_lane, lane_map[target_lane])
            target_gap_back = self._get_backward_gap(veh, target_lane, lane_map[target_lane])

            # Two-wheelers in weak discipline can filter if there's even minimal room
            if veh.veh_type == TYPE_TWO_WHEELER and self.lane_discipline == LANE_DISCIPLINE_WEAK:
                # Weaving/filtering incentive: gap ahead in other lane is at least 1 cell and >= current gap
                has_incentive = (target_gap_ahead > curr_gap) or (curr_gap < veh.speed + 1 and target_gap_ahead >= 1)
                safe_back = target_gap_back >= 1
                p_change = self.p_change_tw
            else:
                # Standard incentive: obstructed in current lane and significantly better ahead
                has_incentive = (curr_gap < min(veh.speed + 1, veh.max_speed)) and (target_gap_ahead > curr_gap)
                # Safe gap behind: follower in target lane should not be forced into immediate crash
                safe_back = target_gap_back >= 2  # safe braking cushion
                p_change = self.p_change_tw if veh.veh_type == TYPE_TWO_WHEELER else self.p_change_car

            # Stochastic lane change execution
            if has_incentive and safe_back and (self.rng.rand() < p_change):
                intended_changes.append((veh, target_lane))
                claimed_cells.add(target_cell)
                claimed_cells.discard((curr_lane, pos))

        # Apply lane changes
        for veh, target_lane in intended_changes:
            veh.lane = target_lane

    def _inflow_phase(self):
        """Generates new vehicles at open road entry (pos 0) according to arrival demand."""
        if self.is_circular:
            return

        cell_map, _ = self._get_grid_maps()
        # Inflow arrival probability based on density
        p_arrival = min(0.95, self.config.density * 1.5)

        for lane in range(self.num_lanes):
            if (lane, 0) not in cell_map:
                if self.rng.rand() < p_arrival:
                    is_tw = self.rng.rand() < self.two_wheeler_share
                    v_type = TYPE_TWO_WHEELER if is_tw else TYPE_CAR
                    v_max = self.config.max_speed_two_wheeler if is_tw else self.config.max_speed_car
                    p_slow = self.config.slowdown_two_wheeler if is_tw else self.config.slowdown_car

                    new_veh = Vehicle(
                        veh_id=self.next_veh_id,
                        veh_type=v_type,
                        pos=0,
                        lane=lane,
                        speed=self.rng.randint(1, min(v_max, 3) + 1),
                        max_speed=v_max,
                        slowdown_prob=p_slow,
                        entry_step=self.current_step
                    )
                    self.next_veh_id += 1
                    self.vehicles.append(new_veh)
                    cell_map[(lane, 0)] = new_veh

    def step(self):
        """Advances the simulation by one step."""
        # 1. Lane changing
        self._lane_changing_phase()

        # 2. Longitudinal update (Acceleration, Signal/Braking, Dawdling, Move)
        _, lane_map = self._get_grid_maps()
        signal_green = self.is_green()
        new_speeds: Dict[int, int] = {}
        step_crossings = 0

        for veh in self.vehicles:
            v = veh.speed
            # Rule A: Acceleration
            v = min(v + 1, veh.max_speed)

            # Rule B: Braking for vehicle ahead
            gap_veh = self._get_forward_gap(veh, veh.lane, lane_map[veh.lane])
            
            # Braking for traffic signal (if red and vehicle is upstream of the stop line)
            effective_gap = gap_veh
            if (not self.is_circular) and (not signal_green):
                if veh.pos < self.signal_pos:
                    signal_gap = self.signal_pos - veh.pos - 1
                    effective_gap = min(effective_gap, signal_gap)

            v = min(v, effective_gap)

            # Rule C: Random dawdling / slowdown
            if v > 0 and self.rng.rand() < veh.slowdown_prob:
                v -= 1

            new_speeds[veh.veh_id] = v

        # Rule D: Movement & Outflow
        surviving_vehicles: List[Vehicle] = []
        for veh in self.vehicles:
            old_pos = veh.pos
            veh.speed = new_speeds[veh.veh_id]
            new_pos = old_pos + veh.speed

            # Check if vehicle crossed the stop line during this step
            if (not self.is_circular) and old_pos < self.signal_pos <= new_pos:
                step_crossings += 1

            # Update waiting count if queued
            if veh.speed == 0:
                veh.waited_steps += 1

            if self.is_circular:
                veh.pos = new_pos % self.road_length
                surviving_vehicles.append(veh)
            else:
                if new_pos < self.road_length:
                    veh.pos = new_pos
                    surviving_vehicles.append(veh)
                else:
                    # Vehicle exited the open road segment
                    veh.exit_step = self.current_step
                    veh.travel_time = self.current_step - veh.entry_step
                    self.completed_trips.append(veh)

        self.vehicles = surviving_vehicles
        self.detector_crossings += step_crossings

        # 3. Inflow at road entrance
        self._inflow_phase()

        # Metrics recording
        self.current_step += 1
        speeds = [v.speed for v in self.vehicles]
        mean_speed = float(np.mean(speeds)) if speeds else 0.0
        total_cells = self.road_length * self.num_lanes
        density = len(self.vehicles) / total_cells
        flow = density * mean_speed

        # Calculate queue behind signal
        queue_len = self._calculate_queue_length()

        self.history_mean_speed.append(mean_speed)
        self.history_density.append(density)
        self.history_flow.append(flow)
        self.history_queue_length.append(queue_len)
        self.history_signal_state.append("green" if signal_green else "red")

    def _calculate_queue_length(self) -> int:
        """
        Calculates queue length in cells upstream of signal stop line.
        Defined as distance from stop line back to furthest contiguous vehicle with speed <= 1.
        """
        if self.is_circular:
            # Count stopped vehicles in entire road
            return sum(1 for v in self.vehicles if v.speed <= 1)

        upstream_slow = [v for v in self.vehicles if v.pos < self.signal_pos and v.speed <= 1]
        if not upstream_slow:
            return 0
        min_pos = min(v.pos for v in upstream_slow)
        return self.signal_pos - min_pos

    def run_all(self) -> Dict[str, Any]:
        """Runs the simulation for all configured steps and calculates summary stats."""
        while self.current_step < self.steps:
            self.step()

        # Compute steady-state metrics
        start_idx = min(self.warmup, len(self.history_flow) - 1)
        ss_flow = float(np.mean(self.history_flow[start_idx:])) if self.history_flow else 0.0
        ss_speed = float(np.mean(self.history_mean_speed[start_idx:])) if self.history_mean_speed else 0.0
        ss_density = float(np.mean(self.history_density[start_idx:])) if self.history_density else 0.0
        mean_queue = float(np.mean(self.history_queue_length[start_idx:])) if self.history_queue_length else 0.0
        max_queue = int(np.max(self.history_queue_length[start_idx:])) if self.history_queue_length else 0

        # Travel time from completed trips that exited during or after warmup
        measured_trips = [t for t in self.completed_trips if t.exit_step is not None and t.exit_step >= self.warmup]
        if not measured_trips and self.completed_trips:
            measured_trips = self.completed_trips

        if measured_trips:
            mean_travel_time = float(np.mean([t.travel_time for t in measured_trips]))
        else:
            mean_travel_time = float(self.road_length / max(0.1, ss_speed))

        # Throughput: completed vehicles per step exiting during measurement period
        active_steps = max(1, self.steps - self.warmup)
        if not self.is_circular:
            throughput = len(measured_trips) / active_steps
            if throughput == 0.0 and self.detector_crossings > 0:
                throughput = self.detector_crossings / self.steps
        else:
            throughput = ss_flow

        # Breakdown by vehicle type
        cars_completed = [t for t in measured_trips if t.veh_type == TYPE_CAR]
        tw_completed = [t for t in measured_trips if t.veh_type == TYPE_TWO_WHEELER]
        car_tt = float(np.mean([t.travel_time for t in cars_completed])) if cars_completed else mean_travel_time
        tw_tt = float(np.mean([t.travel_time for t in tw_completed])) if tw_completed else mean_travel_time

        return {
            "model": "Mumbai_Extended",
            "road_length": self.road_length,
            "density": ss_density,
            "vehicle_count": len(self.vehicles),
            "completed_trips": len(self.completed_trips),
            "throughput": throughput,
            "mean_flow": ss_flow,
            "mean_speed": ss_speed,
            "mean_travel_time": mean_travel_time,
            "car_travel_time": car_tt,
            "two_wheeler_travel_time": tw_tt,
            "mean_queue_length": mean_queue,
            "max_queue_length": max_queue,
            "signal_crossings": self.detector_crossings,
            "two_wheeler_share": self.two_wheeler_share,
            "lane_discipline": self.lane_discipline,
            "total_steps": self.current_step,
            "warmup_steps": self.warmup,
        }

    def get_state(self) -> Dict[str, Any]:
        """Returns full state representation for web UI animation."""
        return {
            "step": self.current_step,
            "signal_state": "green" if self.is_green() else "red",
            "signal_position": self.signal_pos,
            "road_length": self.road_length,
            "num_lanes": self.num_lanes,
            "queue_length": self._calculate_queue_length(),
            "vehicles": [v.to_dict() for v in self.vehicles],
            "completed_count": len(self.completed_trips),
            "mean_speed": round(float(np.mean([v.speed for v in self.vehicles])), 2) if self.vehicles else 0.0,
            "flow": round(float(self.history_flow[-1]), 4) if self.history_flow else 0.0,
            "mean_travel_time": round(float(np.mean([t.travel_time for t in self.completed_trips])), 1) if self.completed_trips else 0.0,
            "active_vehicles": len(self.vehicles)
        }
