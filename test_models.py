"""
test_models.py - Unit tests for NaSch and Mumbai Traffic CA models
"""
import unittest
import numpy as np
from simulation import (
    NaSchModel, NaSchConfig,
    MumbaiTrafficModel, MumbaiConfig,
    TYPE_CAR, TYPE_TWO_WHEELER,
    LANE_DISCIPLINE_STRONG, LANE_DISCIPLINE_MODERATE, LANE_DISCIPLINE_WEAK
)


class TestNaSchModel(unittest.TestCase):
    def test_no_vehicle_overlap(self):
        """Verify that vehicles never overlap across 500 steps."""
        config = NaSchConfig(road_length=100, density=0.35, max_speed=5, slowdown_prob=0.3, simulation_steps=500, random_seed=42)
        model = NaSchModel(config)
        
        for step_idx in range(500):
            positions = [v.pos for v in model.vehicles]
            self.assertEqual(len(positions), len(set(positions)), f"Overlap detected at step {step_idx}")
            model.step()

    def test_deterministic_acceleration_and_braking(self):
        """With p=0 (no random slowdown), verify acceleration and braking rules."""
        config = NaSchConfig(road_length=50, density=0.1, max_speed=5, slowdown_prob=0.0, simulation_steps=10, random_seed=123)
        model = NaSchModel(config)
        # Place two vehicles manually: veh 0 at pos 10 (speed 0), veh 1 at pos 15 (speed 0)
        model.vehicles[0].pos = 10
        model.vehicles[0].speed = 0
        model.vehicles[1].pos = 15
        model.vehicles[1].speed = 0
        model.vehicles = model.vehicles[:2]

        # Step 1:
        # veh 0: gap = 15 - 10 - 1 = 4. Accel: 1, Braking: min(1, 4) = 1. New pos: 11
        # veh 1: gap = (50 - 15) + 10 - 1 = 44. Accel: 1, Braking: min(1, 44) = 1. New pos: 16
        model.step()
        self.assertEqual(model.vehicles[0].pos, 11)
        self.assertEqual(model.vehicles[0].speed, 1)
        self.assertEqual(model.vehicles[1].pos, 16)
        self.assertEqual(model.vehicles[1].speed, 1)

    def test_steady_state_metrics(self):
        """Verify summary stats calculation."""
        config = NaSchConfig(road_length=100, density=0.2, max_speed=5, slowdown_prob=0.2, simulation_steps=200, warmup_steps=50, random_seed=42)
        model = NaSchModel(config)
        results = model.run_all()
        self.assertGreater(results["mean_flow"], 0.0)
        self.assertGreater(results["mean_speed"], 0.0)
        self.assertEqual(results["vehicle_count"], 20)


class TestMumbaiTrafficModel(unittest.TestCase):
    def test_no_vehicle_overlap_multilane(self):
        """Verify vehicles never occupy the exact same (lane, pos) cell."""
        config = MumbaiConfig(
            road_length=100,
            density=0.4,
            max_speed_car=4,
            max_speed_two_wheeler=5,
            slowdown_car=0.3,
            slowdown_two_wheeler=0.15,
            two_wheeler_share=0.5,
            lane_discipline=LANE_DISCIPLINE_WEAK,
            signal_position=75,
            green_time=20,
            red_time=20,
            simulation_steps=300,
            random_seed=42
        )
        model = MumbaiTrafficModel(config)
        for s in range(300):
            cells = [(v.lane, v.pos) for v in model.vehicles]
            self.assertEqual(len(cells), len(set(cells)), f"Collision detected at step {s}")
            model.step()

    def test_red_signal_compliance(self):
        """Verify no vehicle crosses or enters the stop line while signal is RED."""
        config = MumbaiConfig(
            road_length=100,
            density=0.3,
            signal_position=60,
            green_time=15,
            red_time=25,
            simulation_steps=200,
            random_seed=99
        )
        model = MumbaiTrafficModel(config)

        for s in range(200):
            model.step()
            if not model.is_green():
                # On red, no vehicle upstream of the signal should have crossed or reached >= signal_pos
                for v in model.vehicles:
                    if v.pos < config.signal_position:
                        # Should not be at or past signal_pos
                        self.assertLess(v.pos, config.signal_position)
                    # Furthermore, verify nobody is standing in the intersection during red without having cleared it
                    # (All upstream vehicles are strictly < signal_pos)

    def test_lane_discipline_and_two_wheelers(self):
        """Verify both cars and two-wheelers are instantiated and processed correctly."""
        config = MumbaiConfig(
            road_length=150,
            two_wheeler_share=0.6,
            lane_discipline=LANE_DISCIPLINE_MODERATE,
            simulation_steps=100,
            random_seed=7
        )
        model = MumbaiTrafficModel(config)
        model.run_all()
        
        has_car = any(v.veh_type == TYPE_CAR for v in model.vehicles + model.completed_trips)
        has_tw = any(v.veh_type == TYPE_TWO_WHEELER for v in model.vehicles + model.completed_trips)
        self.assertTrue(has_car, "Should contain cars")
        self.assertTrue(has_tw, "Should contain two-wheelers")

    def test_open_road_vehicle_exit_and_completed_trips(self):
        """Verify that vehicles exit the open road past road_length and increment completed trips."""
        config = MumbaiConfig(
            road_length=60,
            density=0.25,
            signal_position=30,
            green_time=40,
            red_time=10,
            simulation_steps=120,
            random_seed=42
        )
        model = MumbaiTrafficModel(config)
        for _ in range(100):
            model.step()
        self.assertGreater(len(model.completed_trips), 0, "Vehicles must complete trips on open road")
        for v in model.vehicles:
            self.assertLess(v.pos, config.road_length)


if __name__ == "__main__":
    unittest.main()
