"""All business logic (no web framework here, so it is easy to test)."""
import hashlib, os, secrets, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.state_machine import Table

EVIDENCE = ("OCCUPIED", "EMPTY", "UNCERTAIN")


def _hash(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()


class Service:
    def __init__(self, store, table_ids=("T1", "T2", "T3"), **table_params):
        self.store = store
        self.tables = {t: Table(t, **table_params) for t in table_ids}
        self.clock = None                  # latest time seen from the video (same clock as evidence)
        self.first_ts, self.last_ts, self.vacant_ts = {}, {}, {}
        self.tokens = {}
        self._defaults()

    # ---------- setup
    def _defaults(self):
        if not self.store.all("staff_users"):
            for name, pw, role in (("staff", "staff123", "staff"), ("manager", "manager123", "manager")):
                salt = secrets.token_hex(8)
                self.store.insert("staff_users", {"name": name, "salt": salt, "hash": _hash(pw, salt), "role": role})
        if not self.store.all("settings"):
            self.store.replace("settings", [{"retention_days": 30, "camera_name": "Camera 1"}])

    def now(self):
        return self.clock if self.clock is not None else time.time()

    # ---------- login
    def login(self, name, password):
        for u in self.store.all("staff_users"):
            if u["name"] == name and u["hash"] == _hash(password, u["salt"]):
                token = secrets.token_hex(16)
                self.tokens[token] = {"name": u["name"], "role": u["role"]}
                return token, u["role"]
        raise ValueError("wrong username or password")

    def user(self, token):
        return self.tokens.get(token)

    # ---------- saving what the state machine did
    def _flush(self, tid, sessions_before):
        tb = self.tables[tid]
        for e in tb.pop_events():
            self.store.insert("status_events", {"table_id": tid, **e})
            if e["to"] == "VACANT":
                self.vacant_ts[tid] = e["ts"]
        for s, e in tb.sessions[sessions_before:]:
            self.store.insert("sessions", {"table_id": tid, "start": s, "end": e, "duration": e - s})

    # ---------- evidence from the vision script
    def evidence(self, tid, ev, ts, people=0):
        if tid not in self.tables:
            raise KeyError("unknown table " + tid)
        if ev not in EVIDENCE:
            raise ValueError("bad evidence")
        self.clock = ts if self.clock is None else max(self.clock, ts)
        self.first_ts.setdefault(tid, ts)
        self.last_ts[tid] = ts
        tb = self.tables[tid]
        n = len(tb.sessions)
        tb.evidence(ev, ts)
        self._flush(tid, n)

    # ---------- staff actions
    def _staff(self, tid, fn):
        tb = self.tables[tid]
        n = len(tb.sessions)
        fn(tb, self.now())
        self._flush(tid, n)

    def cleaning(self, tid, who):
        self._staff(tid, lambda tb, ts: tb.staff_cleaning(ts, who))

    def ready(self, tid, who):
        self._staff(tid, lambda tb, ts: tb.staff_ready(ts, who))

    def set_state(self, tid, state, who):
        self._staff(tid, lambda tb, ts: tb.staff_set(state, ts, who))

    # ---------- what the dashboard shows
    def tables_view(self):
        now, out = self.now(), []
        for tid, tb in self.tables.items():
            dining = 0
            if tb.state == "OCCUPIED" and tb.session_start is not None:
                dining = now - tb.session_start
            elif tb.sessions:
                dining = tb.sessions[-1][1] - tb.sessions[-1][0]
            turnover = now - self.vacant_ts[tid] if tb.state in ("VACANT", "CLEANING") and tid in self.vacant_ts else 0
            out.append({"id": tid, "state": tb.state, "uncertain": tb.state == "UNCERTAIN",
                        "dining_seconds": round(dining), "turnover_seconds": round(turnover)})
        return out

    def sessions(self):
        return sorted(self.store.all("sessions"), key=lambda s: s["start"], reverse=True)

    # ---------- zones, settings
    def set_zone(self, tid, polygon):
        zones = [z for z in self.store.all("zones") if z["table_id"] != tid]
        zones.append({"table_id": tid, "polygon": polygon})
        self.store.replace("zones", zones)

    def zones(self):
        return self.store.all("zones")

    def settings(self):
        return self.store.all("settings")[0]

    def update_settings(self, retention_days=None, camera_name=None):
        s = self.settings()
        if retention_days is not None:
            if int(retention_days) < 1:
                raise ValueError("retention_days must be at least 1")
            s["retention_days"] = int(retention_days)
        if camera_name is not None:
            s["camera_name"] = str(camera_name)
        self.store.replace("settings", [s])
        return s

    # ---------- privacy: delete old records
    def purge(self):
        cutoff = self.now() - self.settings()["retention_days"] * 86400
        sess, ev = self.store.all("sessions"), self.store.all("status_events")
        keep_s = [s for s in sess if s["end"] >= cutoff]
        keep_e = [e for e in ev if e["ts"] >= cutoff]
        self.store.replace("sessions", keep_s)
        self.store.replace("status_events", keep_e)
        return {"deleted_sessions": len(sess) - len(keep_s), "deleted_events": len(ev) - len(keep_e)}

    # ---------- analytics (calculated when asked)
    def analytics(self):
        sessions, events = self.store.all("sessions"), self.store.all("status_events")
        out = {"utilisation": {}, "sessions_per_hour": {}}
        durs = [s["duration"] for s in sessions]
        for tid, tb in self.tables.items():
            if tid not in self.first_ts:
                continue
            observed = max(self.last_ts[tid] - self.first_ts[tid], 1)
            busy = sum(s["duration"] for s in sessions if s["table_id"] == tid)
            if tb.state == "OCCUPIED" and tb.session_start is not None:
                busy += self.last_ts[tid] - tb.session_start
            out["utilisation"][tid] = round(min(busy / observed, 1.0), 3)
        for tid, tb in self.tables.items():        # a running session also counts as a session
            if tb.state == "OCCUPIED" and tb.session_start is not None:
                durs.append(self.last_ts[tid] - tb.session_start)
        out["session_count"] = len(durs)
        out["avg_dining_seconds"] = round(sum(durs) / len(durs)) if durs else None
        for s in sessions:
            h = time.strftime("%Y-%m-%d %H:00", time.localtime(s["start"]))
            out["sessions_per_hour"][h] = out["sessions_per_hour"].get(h, 0) + 1
        clear, clean, idle = [], [], []
        for tid in self.tables:
            ev = sorted([e for e in events if e["table_id"] == tid], key=lambda e: e["ts"])
            starts = sorted(s["start"] for s in sessions if s["table_id"] == tid)
            tv = tc = tr = None
            for e in ev:
                if e["to"] == "VACANT":
                    tv, tc, tr = e["ts"], None, None
                elif e["to"] == "CLEANING" and tv is not None:
                    tc = e["ts"]; clear.append(tc - tv)
                elif e["to"] == "READY" and tc is not None:
                    tr = e["ts"]; clean.append(tr - tc)
                    nxt = [s for s in starts if s > tr]
                    if nxt:
                        idle.append(nxt[0] - tr)
        avg = lambda xs: round(sum(xs) / len(xs)) if xs else None
        out["turnover"] = {"vacant_to_cleaning": avg(clear), "cleaning_to_ready": avg(clean), "ready_to_next_seating": avg(idle)}
        unc = obs = 0
        for tid in self.tables:
            if tid not in self.first_ts:
                continue
            obs += max(self.last_ts[tid] - self.first_ts[tid], 1)
            ev = sorted([e for e in events if e["table_id"] == tid], key=lambda e: e["ts"])
            start = None
            for e in ev:
                if e["to"] == "UNCERTAIN":
                    start = e["ts"]
                elif e["from"] == "UNCERTAIN" and start is not None:
                    unc += e["ts"] - start; start = None
            if start is not None:
                unc += self.last_ts[tid] - start
        out["uncertain_share"] = round(unc / obs, 3) if obs else 0
        return out
