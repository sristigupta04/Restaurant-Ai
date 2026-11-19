"""Small helpers used by pipeline.py (no YOLO needed, so they can be tested)."""
import cv2
import numpy as np


def to_polys(zones):
    return {k: np.array(v, np.int32) for k, v in zones.items()}


def foot_point(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, float(y2))              # bottom centre of the person box


def inside(poly, p):
    return cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), False) >= 0


def depth_inside(poly, p):
    """Distance in pixels from the polygon edge (positive = inside)."""
    return cv2.pointPolygonTest(poly, (float(p[0]), float(p[1])), True)


class ZoneTracker:
    """Turns 'who is in each zone' into evidence: OCCUPIED / EMPTY / UNCERTAIN.

    UNCERTAIN when:  (1) people in the zone have low average confidence, or
                     (2) a person vanished DEEP inside the zone (probably hidden, not left).
    A hidden person is waited for at most hidden_limit seconds, then treated as EMPTY.
    """

    def __init__(self, polys, low_conf=0.5, margin=25, hidden_limit=60):
        self.polys, self.low_conf, self.margin, self.hidden_limit = polys, low_conf, margin, hidden_limit
        self.had = {z: False for z in polys}
        self.last_pt = {z: None for z in polys}
        self.lost_since = {z: None for z in polys}

    def update(self, t, found):
        """found: {zone: [((x, y), confidence), ...]} for this frame. Returns {zone: (evidence, people)}."""
        out = {}
        for z, poly in self.polys.items():
            pts = found.get(z, [])
            if pts:
                self.had[z], self.last_pt[z], self.lost_since[z] = True, pts[-1][0], None
                mean_conf = sum(c for _, c in pts) / len(pts)
                out[z] = ("UNCERTAIN" if mean_conf < self.low_conf else "OCCUPIED", len(pts))
            elif self.had[z] and self.last_pt[z] is not None and depth_inside(poly, self.last_pt[z]) >= self.margin:
                if self.lost_since[z] is None:
                    self.lost_since[z] = t
                if t - self.lost_since[z] < self.hidden_limit:
                    out[z] = ("UNCERTAIN", 0)
                else:
                    self.had[z] = False; out[z] = ("EMPTY", 0)
            else:
                self.had[z], self.lost_since[z] = False, None
                out[z] = ("EMPTY", 0)
        return out
