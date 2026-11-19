"""Video -> YOLO + ByteTrack -> zones -> evidence (saved to a file and/or sent to the API).

Example:
  python vision/pipeline.py --clip data/clips/clip02.mp4 --start "2026-11-20 09:00:00" --out data/evidence/clip02.jsonl
  python vision/pipeline.py --clip data/clips/clip07.mp4 --start "2026-11-20 09:00:00" --api http://localhost:8000 --realtime --show
"""
import argparse, collections, json, os, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
from vision.zone_tools import ZoneTracker, foot_point, inside, to_polys


def post(api, body):
    req = urllib.request.Request(api + "/api/evidence", json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception as e:
        print("[api] could not send:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", required=True)
    ap.add_argument("--zones", default="data/zones.json")
    ap.add_argument("--start", default="2026-11-20 09:00:00", help="clock time when the clip started")
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.4)
    ap.add_argument("--stride", type=int, default=4, help="process every Nth frame")
    ap.add_argument("--out", help="save evidence lines to this .jsonl file (used by eval.py)")
    ap.add_argument("--api", help="send evidence to this API, e.g. http://localhost:8000")
    ap.add_argument("--realtime", action="store_true", help="wait so the video plays at normal speed")
    ap.add_argument("--show", action="store_true", help="show a window with boxes and zones (press q to stop)")
    a = ap.parse_args()

    from ultralytics import YOLO                    # imported here so tests do not need it
    zones = json.load(open(a.zones))
    polys = to_polys(zones)
    zt = ZoneTracker(polys)
    base = time.mktime(time.strptime(a.start, "%Y-%m-%d %H:%M:%S"))
    cap = cv2.VideoCapture(a.clip); fps = cap.get(cv2.CAP_PROP_FPS) or 25.0; cap.release()
    out = open(a.out, "w") if a.out else None
    model = YOLO(a.model)
    t0, n, sec, votes, people, last_sent = time.time(), 0, -1, {z: collections.Counter() for z in polys}, {z: 0 for z in polys}, {}

    def emit(second):
        for z in polys:
            c = votes[z]
            if not c:
                continue
            prio = {"OCCUPIED": 2, "UNCERTAIN": 1, "EMPTY": 0}      # tie -> prefer presence
            ev = max(c, key=lambda k: (c[k], prio[k]))                # most common evidence in this second
            line = {"t": second, "table": z, "ev": ev, "people": people[z]}
            if out:
                out.write(json.dumps(line) + "\n")
            if a.api and (last_sent.get(z, (None, -99))[0] != ev or second - last_sent[z][1] >= 5):
                post(a.api, {"table_id": z, "evidence": ev, "ts": base + second, "people": people[z]})
                last_sent[z] = (ev, second)
            votes[z].clear()

    for r in model.track(source=a.clip, classes=[0], conf=a.conf, tracker="bytetrack.yaml",
                         persist=True, stream=True, vid_stride=a.stride, verbose=False):
        t = n * a.stride / fps
        n += 1
        found = {z: [] for z in polys}
        if r.boxes is not None and len(r.boxes):
            for box, conf in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist()):
                p = foot_point(box)
                for z, poly in polys.items():
                    if inside(poly, p):
                        found[z].append((p, conf))
        res = zt.update(t, found)
        if int(t) != sec:
            if sec >= 0:
                emit(sec)
            sec = int(t)
        for z, (ev, ppl) in res.items():
            votes[z][ev] += 1; people[z] = ppl
        if a.realtime:
            time.sleep(max(0, t - (time.time() - t0)))
        if a.show:
            img = r.plot()
            for z, poly in polys.items():
                cv2.polylines(img, [poly], True, (0, 255, 255), 2)
                cv2.putText(img, "%s %s" % (z, res[z][0]), tuple(int(x) for x in poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.imshow("pipeline", cv2.resize(img, None, fx=0.6, fy=0.6))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    emit(sec)
    if out:
        out.close()
    print("done. frames processed:", n)


if __name__ == "__main__":
    main()
