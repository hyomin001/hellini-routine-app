from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from utils import db


class FeatureDatabaseTests(unittest.TestCase):
    def test_save_routine_normalizes_items(self):
        database = SimpleNamespace(routines=MagicMock())
        database.routines.insert_one.return_value = SimpleNamespace(inserted_id=ObjectId())
        with patch.object(db, "get_db", return_value=database):
            ok, _, routine_id = db.save_routine(
                "user-1",
                " 가슴 루틴 ",
                [{"exercise_name": "벤치프레스", "sets": "4", "target_reps": "8~12회"}],
            )
        self.assertTrue(ok)
        self.assertTrue(routine_id)
        saved = database.routines.insert_one.call_args.args[0]
        self.assertEqual(saved["name"], "가슴 루틴")
        self.assertEqual(saved["items"][0]["sets"], 4)
        self.assertEqual(saved["items"][0]["target_reps"], 12)

    def test_start_session_replaces_previous_active_session(self):
        database = SimpleNamespace(workout_sessions=MagicMock())
        database.workout_sessions.insert_one.return_value = SimpleNamespace(inserted_id=ObjectId())
        routine = {"name": "짧게", "items": [{"exercise_name": "스쿼트", "sets": 3, "target_reps": 8}]}
        with patch.object(db, "get_db", return_value=database):
            session_id = db.start_workout_session("user-1", routine, "2026-08-24")
        self.assertTrue(session_id)
        database.workout_sessions.update_many.assert_called_once()
        saved = database.workout_sessions.insert_one.call_args.args[0]
        self.assertEqual(saved["status"], "active")
        self.assertEqual(saved["items"][0]["exercise_name"], "스쿼트")

    def test_body_metric_requires_at_least_one_measurement(self):
        with patch.object(db, "get_db") as get_db:
            ok, message = db.save_body_metric("user-1", "2026-08-24")
        self.assertFalse(ok)
        self.assertIn("하나 이상", message)
        get_db.assert_not_called()

    def test_part_catalog_keeps_base_and_adds_custom_exercise(self):
        custom = {
            "name": "내 가슴 운동",
            "part": "PART1",
            "sets": 3,
            "target_reps": 10,
            "reps": "10회",
            "source": "custom",
            "active": True,
        }
        with patch.object(db, "get_exercise_catalog", return_value=[custom]):
            rows = db.get_exercises_for_part_catalog("user-1", "PART1")
        self.assertIn("내 가슴 운동", [row["name"] for row in rows])
        self.assertGreater(len(rows), 1)

    def test_part_catalog_does_not_restore_disabled_base_exercise(self):
        from utils.data import exercises_for_part

        base = exercises_for_part("PART1")[0]
        disabled = {**base, "base_name": base["name"], "source": "official", "active": False}
        with patch.object(db, "get_exercise_catalog", return_value=[disabled]):
            rows = db.get_exercises_for_part_catalog("user-1", "PART1")
        self.assertNotIn(base["name"], [row["name"] for row in rows])


if __name__ == "__main__":
    unittest.main()
