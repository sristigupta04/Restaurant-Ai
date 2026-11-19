"""Draw table zones on one frame of a clip.

  python vision/zone_editor.py --clip data/clips/calibration.mp4 --tables T1 T2 T3
Mouse: left click adds a corner.   Keys: n = finish this table / next,  u = undo point,  s = save and quit,  q = quit without saving.
"""
import argparse, json, os, urllib.request
import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--clip", required=True)
ap.add_argument("--tables", nargs="+", default=["T1", "T2", "T3"])
ap.add_argument("--out", default="data/zones.json")
ap.add_argument("--api", help="also send zones to the API, e.g. http://localhost:8000")
a = ap.parse_args()

cap = cv2.VideoCapture(a.clip); ok, frame = cap.read(); cap.release()
if not ok:
    raise SystemExit("cannot read the clip")
zones, cur, idx = {}, [], 0


def redraw():
    img = frame.copy()
    for k, pts in zones.items():
        cv2.polylines(img, [np.array(pts, np.int32)], True, (0, 255, 255), 2)
        cv2.putText(img, k, tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    for p in cur:
        cv2.circle(img, tuple(p), 4, (0, 0, 255), -1)
    if len(cur) > 1:
        cv2.polylines(img, [np.array(cur, np.int32)], False, (0, 0, 255), 2)
    cv2.putText(img, "Drawing %s | n=next u=undo s=save q=quit" % a.tables[min(idx, len(a.tables) - 1)], (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.imshow("zones", img)


def click(e, x, y, f, p):
    if e == cv2.EVENT_LBUTTONDOWN:
        cur.append([x, y]); redraw()


cv2.namedWindow("zones"); cv2.setMouseCallback("zones", click); redraw()
while True:
    k = cv2.waitKey(20) & 0xFF
    if k == ord("u") and cur:
        cur.pop(); redraw()
    elif k == ord("n") and len(cur) >= 3 and idx < len(a.tables):
        zones[a.tables[idx]] = cur[:]; cur.clear(); idx += 1; redraw()
    elif k == ord("s"):
        if len(cur) >= 3 and idx < len(a.tables):
            zones[a.tables[idx]] = cur[:]
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        json.dump(zones, open(a.out, "w"), indent=1)
        print("saved", a.out, list(zones))
        if a.api:
            for t, pts in zones.items():
                req = urllib.request.Request(a.api + "/api/zones", json.dumps({"table_id": t, "polygon": pts}).encode(), {"Content-Type": "application/json"})
                try: urllib.request.urlopen(req, timeout=2).read()
                except Exception as e: print("api error", e)
        break
    elif k == ord("q"):
        break
cv2.destroyAllWindows()
