import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.eval import evaluate


def ev(table, label, a, b): return [{"t": t, "table": table, "ev": label, "people": 1} for t in range(a, b)]


class T(unittest.TestCase):
    def test_perfect_clip(self):
        evs = ev("T1", "EMPTY", 0, 15) + ev("T1", "OCCUPIED", 15, 105) + ev("T1", "EMPTY", 105, 150)
        gt = [("T1", "EMPTY", 0, 15), ("T1", "OCCUPIED", 15, 105), ("T1", "EMPTY", 105, 150)]
        r = evaluate(evs, gt, t_occ=10, t_vac=30)
        self.assertGreater(r["f1"], 0.98); self.assertEqual(r["false_events"], 0); self.assertEqual(r["missed_events"], 0)
        self.assertEqual(r["start_error_s"], 0.0)

    def test_passing_person_is_not_an_event(self):
        evs = ev("T1", "EMPTY", 0, 20) + ev("T1", "OCCUPIED", 20, 25) + ev("T1", "EMPTY", 25, 80)
        gt = [("T1", "EMPTY", 0, 80)]
        r = evaluate(evs, gt, t_occ=10, t_vac=30)
        self.assertEqual(r["false_events"], 0)

    def test_missed_session_is_counted(self):
        evs = ev("T1", "EMPTY", 0, 100)
        gt = [("T1", "OCCUPIED", 20, 80)]
        self.assertEqual(evaluate(evs, gt)["missed_events"], 1)


if __name__ == "__main__":
    unittest.main()
