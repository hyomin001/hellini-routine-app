import unittest
from datetime import date

from utils.training import (
    estimate_one_rep_max,
    normalize_routine_items,
    parse_target_reps,
    progression_recommendation,
    recommend_exercises,
    volume_by_part,
    weekly_training_summary,
)


class TrainingLogicTests(unittest.TestCase):
    def test_parse_target_reps_uses_range_upper_bound(self):
        self.assertEqual(parse_target_reps("8~12회"), 12)
        self.assertEqual(parse_target_reps("10회"), 10)

    def test_normalize_routine_items_deduplicates_and_clamps(self):
        rows = normalize_routine_items(
            [
                {"name": "스쿼트", "sets": 3, "reps": "8~12회", "part": "PART5"},
                {"exercise_name": "스쿼트", "sets": 5, "target_reps": 5},
                {"exercise_name": "", "sets": 2},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target_reps"], 12)

    def test_progression_recommends_weight_after_all_sets_hit(self):
        result = progression_recommendation([{"w": "40", "r": "10"}, {"w": "40", "r": "10"}], 10)
        self.assertTrue(result["ready"])
        self.assertEqual(result["suggested_weight"], 42.5)

    def test_progression_holds_weight_when_target_is_missed(self):
        result = progression_recommendation([{"w": "40", "r": "10"}, {"w": "40", "r": "8"}], 10)
        self.assertFalse(result["ready"])
        self.assertEqual(result["suggested_weight"], 40)

    def test_estimated_one_rep_max(self):
        self.assertAlmostEqual(estimate_one_rep_max(60, 10), 80.0)

    def test_weekly_summary_combines_strength_and_cardio_days(self):
        summary = weekly_training_summary(
            [
                {"date": "2026-08-24", "sets": [{"w": "10", "r": "10"}]},
                {"date": "2026-08-16", "sets": [{"w": "20", "r": "5"}]},
            ],
            [{"date": "2026-08-23"}],
            today=date(2026, 8, 24),
        )
        self.assertEqual(summary["current_days"], 2)
        self.assertEqual(summary["previous_days"], 1)
        self.assertEqual(summary["current_volume"], 100)

    def test_volume_by_part(self):
        result = volume_by_part(
            [{"exercise_name": "스쿼트", "sets": [{"w": 100, "r": 5}]}],
            {"스쿼트": "하체·엉덩이"},
        )
        self.assertEqual(result["하체·엉덩이"], 500)

    def test_recommend_exercises_balances_parts_and_uses_official_only(self):
        import random

        catalog = [
            {"name": "가슴1", "part": "PART1", "source": "official", "active": True},
            {"name": "가슴2", "part": "PART1", "source": "official", "active": True},
            {"name": "등1", "part": "PART2", "source": "official", "active": True},
            {"name": "내 운동", "part": "PART1", "source": "custom", "active": True},
            {"name": "숨김", "part": "PART2", "source": "official", "active": False},
        ]
        rows = recommend_exercises(catalog, ["PART1", "PART2"], 3, random.Random(1))
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["part"] for row in rows}, {"PART1", "PART2"})
        self.assertNotIn("내 운동", [row["name"] for row in rows])


if __name__ == "__main__":
    unittest.main()
