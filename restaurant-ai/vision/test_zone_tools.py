import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vision.zone_tools import ZoneTracker, to_polys, foot_point


class T(unittest.TestCase):
    def zt(self): return ZoneTracker(to_polys({"T1": [[100, 100], [300, 100], [300, 300], [100, 300]]}), hidden_limit=60)

    def test_person_inside_is_occupied(self):
        self.assertEqual(self.zt().update(0, {"T1": [((200, 200), 0.9)]})["T1"][0], "OCCUPIED")

    def test_low_confidence_is_uncertain(self):
        self.assertEqual(self.zt().update(0, {"T1": [((200, 200), 0.3)]})["T1"][0], "UNCERTAIN")

    def test_vanishing_deep_inside_is_uncertain_then_empty(self):
        z = self.zt(); z.update(0, {"T1": [((200, 200), 0.9)]})
        self.assertEqual(z.update(5, {})["T1"][0], "UNCERTAIN")
        self.assertEqual(z.update(70, {})["T1"][0], "EMPTY")

    def test_leaving_through_edge_is_empty(self):
        z = self.zt(); z.update(0, {"T1": [((105, 200), 0.9)]})     # 5 px from the edge
        self.assertEqual(z.update(1, {})["T1"][0], "EMPTY")

    def test_never_seen_is_empty(self):
        self.assertEqual(self.zt().update(0, {})["T1"][0], "EMPTY")

    def test_foot_point(self):
        self.assertEqual(foot_point((0, 0, 10, 20)), (5.0, 20.0))


if __name__ == "__main__":
    unittest.main()
