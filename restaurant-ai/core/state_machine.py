"""Table state machine - the heart of the project.

States: OCCUPIED, VACANT (needs cleaning), CLEANING, READY, UNCERTAIN.
Evidence from the camera is only: OCCUPIED, EMPTY or UNCERTAIN.
Only STAFF can move a table to CLEANING and READY.
All times are in seconds (any clock, as long as it is the same everywhere).
"""
T_OCC, T_VAC, T_UNC, T_FLICK = 10, 30, 8, 3   # test-scale values (clips are short)


class Table:
    def __init__(self, tid, t_occ=None, t_vac=None, t_unc=None, t_flick=None, start_state="READY"):
        self.id = tid
        self.t_occ = T_OCC if t_occ is None else t_occ      # stay this long -> Occupied
        self.t_vac = T_VAC if t_vac is None else t_vac      # empty this long -> Vacant
        self.t_unc = T_UNC if t_unc is None else t_unc      # unsure this long -> Uncertain
        self.t_flick = T_FLICK if t_flick is None else t_flick  # ignore missed detections shorter than this
        self.state = start_state            # start status is set by staff (default READY)
        self.first = None                   # when presence started
        self.last = None                    # last time a person was seen
        self.empty_since = None
        self.unc_since = None
        self.before = None                  # state before Uncertain
        self.session_start = None
        self.sessions = []                  # closed sessions: (start, end)
        self._events = []                   # state changes not yet read

    # ---- helpers
    def _set(self, new, ts, who):
        if new != self.state:
            self._events.append({"ts": ts, "from": self.state, "to": new, "by": who})
            self.state = new

    def pop_events(self):
        ev, self._events = self._events, []
        return ev

    # ---- evidence from the camera: "OCCUPIED" / "EMPTY" / "UNCERTAIN"
    def evidence(self, ev, ts):
        if ev == "UNCERTAIN":
            self.unc_since = self.unc_since if self.unc_since is not None else ts
            if ts - self.unc_since >= self.t_unc and self.state != "UNCERTAIN":
                self.before = self.state
                self._set("UNCERTAIN", ts, "system")
            return
        if ev not in ("OCCUPIED", "EMPTY"):
            raise ValueError("unknown evidence: %r" % (ev,))
        self.unc_since = None
        if self.state == "UNCERTAIN":                       # evidence is good again
            self._set(self.before or "READY", ts, "system")
        if ev == "OCCUPIED":
            self.last, self.empty_since = ts, None
            self.first = self.first if self.first is not None else ts
            if self.state != "OCCUPIED" and ts - self.first >= self.t_occ:
                self.session_start = self.first            # session starts at first stable presence
                self._set("OCCUPIED", ts, "system")
        else:
            self.empty_since = self.empty_since if self.empty_since is not None else ts
            if ts - self.empty_since >= self.t_flick:
                self.first = None                          # a real gap, not a missed detection
            if self.state == "OCCUPIED" and ts - self.empty_since >= self.t_vac:
                self.sessions.append((self.session_start, self.last))   # session ends at last time seen
                self._set("VACANT", ts, "system")

    # ---- staff actions
    def staff_cleaning(self, ts, who):
        if self.state != "VACANT":
            raise ValueError("table is not Vacant")
        self._set("CLEANING", ts, who)

    def staff_ready(self, ts, who):                  # the ONLY way to reach READY after a session
        if self.state != "CLEANING":
            raise ValueError("table is not in Cleaning")
        self._set("READY", ts, who)

    def staff_set(self, new, ts, who):
        """Staff resolves an Uncertain table or sets the start status."""
        if new not in ("READY", "VACANT", "OCCUPIED"):
            raise ValueError("invalid status")
        if not (self.state == "UNCERTAIN" or (not self.sessions and self.state != "OCCUPIED")):
            raise ValueError("status can only be set when Uncertain or at the start")
        self.first = self.empty_since = self.unc_since = None
        if new == "OCCUPIED":
            self.session_start, self.last = ts, ts
        self._set(new, ts, who)
