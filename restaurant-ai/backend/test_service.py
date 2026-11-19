import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.db import FileStore
from backend.service import Service


class T(unittest.TestCase):
    def svc(self):
        return Service(FileStore(os.path.join(tempfile.mkdtemp(), "s.json")), t_occ=10, t_vac=30, t_unc=8, t_flick=3)

    def run_clip(self, s, tid, pattern):            # pattern: [(evidence, t0, t1)]
        for ev, a, b in pattern:
            for t in range(a, b):
                s.evidence(tid, ev, 1000 + t)

    def test_full_cycle_and_analytics(self):
        s = self.svc()
        self.run_clip(s, "T1", [("OCCUPIED", 0, 60), ("EMPTY", 60, 100)])
        self.assertEqual(s.tables_view()[0]["state"], "VACANT")
        s.cleaning("T1", "staff"); s.clock += 20; s.ready("T1", "staff")
        self.run_clip(s, "T1", [("EMPTY", 140, 150), ("OCCUPIED", 150, 200), ("EMPTY", 200, 240)])
        a = s.analytics()
        self.assertEqual(a["session_count"], 2)
        self.assertEqual(a["turnover"]["cleaning_to_ready"], 20)
        self.assertIsNotNone(a["turnover"]["ready_to_next_seating"])
        self.assertGreater(a["utilisation"]["T1"], 0.4)
        self.assertEqual(len(s.sessions()), 2)

    def test_ready_refused_before_cleaning(self):
        s = self.svc(); self.run_clip(s, "T1", [("OCCUPIED", 0, 60), ("EMPTY", 60, 100)])
        with self.assertRaises(ValueError): s.ready("T1", "staff")

    def test_login(self):
        s = self.svc()
        token, role = s.login("manager", "manager123"); self.assertEqual(role, "manager")
        with self.assertRaises(ValueError): s.login("manager", "wrong")

    def test_purge_old_records(self):
        s = self.svc()
        s.store.insert("sessions", {"table_id": "T1", "start": 0, "end": 100, "duration": 100})
        s.store.insert("status_events", {"table_id": "T1", "ts": 50, "from": "READY", "to": "OCCUPIED", "by": "system"})
        s.evidence("T1", "EMPTY", 90 * 86400)       # clock moves 90 days ahead; retention is 30 days
        r = s.purge(); self.assertEqual(r["deleted_sessions"], 1); self.assertEqual(len(s.sessions()), 0)

    def test_uncertain_share(self):
        s = self.svc()
        self.run_clip(s, "T1", [("OCCUPIED", 0, 30), ("UNCERTAIN", 30, 60), ("OCCUPIED", 60, 90)])
        self.assertGreater(s.analytics()["uncertain_share"], 0.1)

    def test_no_image_data_is_stored(self):
        s = self.svc(); self.run_clip(s, "T1", [("OCCUPIED", 0, 30)])
        for coll in ("sessions", "status_events", "staff_users", "settings"):
            for d in s.store.all(coll):
                self.assertFalse(any(isinstance(v, (bytes, bytearray)) for v in d.values()))


if __name__ == "__main__":
    unittest.main()
