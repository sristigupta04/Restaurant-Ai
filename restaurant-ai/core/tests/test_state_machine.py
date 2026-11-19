import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.state_machine import Table


def feed(tb, ev, t0, t1):
    for t in range(t0, t1):
        tb.evidence(ev, t)


class T(unittest.TestCase):
    def tb(self): return Table("T1", t_occ=10, t_vac=30, t_unc=8, t_flick=3)

    def test_sit_and_stay_becomes_occupied(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 12)
        self.assertEqual(tb.state, "OCCUPIED"); self.assertEqual(tb.session_start, 0)

    def test_walk_through_is_ignored(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 5); feed(tb, "EMPTY", 5, 60)
        self.assertEqual(tb.state, "READY"); self.assertEqual(tb.sessions, [])

    def test_short_absence_stays_occupied(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 45); feed(tb, "OCCUPIED", 45, 60)
        self.assertEqual(tb.state, "OCCUPIED"); self.assertEqual(tb.sessions, [])

    def test_long_absence_becomes_vacant_and_session_ends_at_last_seen(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 60)
        self.assertEqual(tb.state, "VACANT"); self.assertEqual(tb.sessions, [(0, 19)])

    def test_new_session_after_return(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 60); feed(tb, "OCCUPIED", 60, 80)
        self.assertEqual(tb.state, "OCCUPIED"); self.assertEqual(tb.session_start, 60)

    def test_vacant_cleaning_ready(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 60)
        tb.staff_cleaning(70, "sristi"); self.assertEqual(tb.state, "CLEANING")
        tb.staff_ready(90, "sristi"); self.assertEqual(tb.state, "READY")

    def test_ready_refused_if_not_cleaning(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 60)
        with self.assertRaises(ValueError): tb.staff_ready(70, "x")      # still Vacant
        tb2 = self.tb()
        with self.assertRaises(ValueError): tb2.staff_ready(5, "x")

    def test_cleaning_refused_if_not_vacant(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20)
        with self.assertRaises(ValueError): tb.staff_cleaning(25, "x")

    def test_empty_table_never_becomes_ready_by_itself(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "EMPTY", 20, 500)
        self.assertEqual(tb.state, "VACANT")                              # waits for staff

    def test_uncertain_after_delay_and_recovers_to_old_state(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20)
        feed(tb, "UNCERTAIN", 20, 25); self.assertEqual(tb.state, "OCCUPIED")   # not yet
        feed(tb, "UNCERTAIN", 25, 35); self.assertEqual(tb.state, "UNCERTAIN")
        tb.evidence("OCCUPIED", 35); self.assertEqual(tb.state, "OCCUPIED")

    def test_empty_scene_never_occupied(self):
        tb = self.tb(); feed(tb, "EMPTY", 0, 300); self.assertEqual(tb.state, "READY")

    def test_missed_detection_flicker_does_not_reset_presence(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 5); feed(tb, "EMPTY", 5, 7); feed(tb, "OCCUPIED", 7, 14)
        self.assertEqual(tb.state, "OCCUPIED"); self.assertEqual(tb.session_start, 0)

    def test_two_tables_are_independent(self):
        a, b = self.tb(), Table("T2", t_occ=10, t_vac=30)
        feed(a, "OCCUPIED", 0, 20); feed(b, "EMPTY", 0, 20)
        self.assertEqual((a.state, b.state), ("OCCUPIED", "READY"))

    def test_staff_can_resolve_uncertain(self):
        tb = self.tb(); feed(tb, "OCCUPIED", 0, 20); feed(tb, "UNCERTAIN", 20, 40)
        tb.staff_set("VACANT", 41, "sristi"); self.assertEqual(tb.state, "VACANT")


if __name__ == "__main__":
    unittest.main()
