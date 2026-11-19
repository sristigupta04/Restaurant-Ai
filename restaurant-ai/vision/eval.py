"""Compare system output with ground truth.

1) Save evidence once per clip:   python vision/pipeline.py --clip ... --out data/evidence/clip03.jsonl
2) Write ground truth CSV:        data/ground_truth/clip03.csv   (table,state,start_s,end_s ; states OCCUPIED/EMPTY/UNCERTAIN)
3) Evaluate (fast, no YOLO):      python vision/eval.py --clips 03 05 06 --t_occ 10 --t_vac 30
   Sweep settings on tuning clips: python vision/eval.py --clips 02 04 05 --sweep
"""
import argparse, csv, itertools, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.state_machine import Table


def load_evidence(path):
    return sorted((json.loads(l) for l in open(path) if l.strip()), key=lambda d: d["t"])


def load_gt(path):
    return [(r["table"], r["state"], float(r["start_s"]), float(r["end_s"])) for r in csv.DictReader(open(path))]


def replay(evs, **params):
    """Run the state machine on saved evidence. Returns {table: (timeline{sec:state}, sessions, uncertain_seconds)}."""
    tabs, tl, unc = {}, {}, {}
    for d in evs:
        t = d["table"]
        tb = tabs.setdefault(t, Table(t, **params)); tl.setdefault(t, {}); unc.setdefault(t, 0)
        tb.evidence(d["ev"], d["t"])
        tl[t][int(d["t"])] = tb.state
    res = {}
    for t, tb in tabs.items():
        sessions = list(tb.sessions)
        if tb.state == "OCCUPIED" and tb.session_start is not None:
            sessions.append((tb.session_start, tb.last))            # session still running at the end
        res[t] = (tl[t], sessions)
    return res


def gt_sessions(gt, table):
    iv = sorted((s, e) for t, st, s, e in gt if t == table and st == "OCCUPIED")
    merged = []
    for s, e in iv:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def evaluate(evs, gt, **params):
    res = replay(evs, **params)
    n = int(max(d["t"] for d in evs)) + 1
    tp = fp = fn = tn = 0
    s_err, e_err, false_ev, missed, unc_sys, unc_gt, total = [], [], 0, 0, 0, 0, 0
    for table, (tl, sess) in res.items():
        truth = [0] * n
        for t, st, s, e in gt:
            if t == table and st == "OCCUPIED":
                for x in range(int(s), min(int(e), n)):
                    truth[x] = 1
        for t, st, s, e in gt:
            if t == table and st == "UNCERTAIN":
                unc_gt += int(e) - int(s)
        pred = [0] * n                                          # back-dated sessions (start = first presence)
        for s, e in sess:
            for x in range(int(s), min(int(e) + 1, n)):
                pred[x] = 1
        for x in range(n):
            if pred[x] and truth[x]: tp += 1
            elif pred[x]: fp += 1
            elif truth[x]: fn += 1
            else: tn += 1
        last = None
        for x in range(n):
            last = tl.get(x, last)
            unc_sys += 1 if last == "UNCERTAIN" else 0
            total += 1
        g = gt_sessions(gt, table)
        used = set()
        for gs, ge in g:
            m = [i for i, (s, e) in enumerate(sess) if s <= ge and e >= gs and i not in used]
            if m:
                i = m[0]; used.add(i); s_err.append(sess[i][0] - gs); e_err.append(sess[i][1] - ge)
            else:
                missed += 1
        false_ev += len([1 for i, (s, e) in enumerate(sess) if i not in used and not any(s <= ge and e >= gs for gs, ge in g)])
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3), "false_events": false_ev,
            "missed_events": missed, "start_error_s": mean(s_err), "end_error_s": mean(e_err),
            "uncertain_system_pct": round(100 * unc_sys / total, 1) if total else 0,
            "uncertain_truth_pct": round(100 * unc_gt / total, 1) if total else 0}


def clip_files(c):
    return "data/evidence/clip%s.jsonl" % c, "data/ground_truth/clip%s.csv" % c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="+", required=True, help="clip numbers, e.g. 02 04 05")
    ap.add_argument("--t_occ", type=float); ap.add_argument("--t_vac", type=float)
    ap.add_argument("--t_unc", type=float); ap.add_argument("--t_flick", type=float)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--csv", help="write results to this csv")
    a = ap.parse_args()
    data = {c: (load_evidence(clip_files(c)[0]), load_gt(clip_files(c)[1])) for c in a.clips}
    if a.sweep:
        rows = []
        for to, tv, tu in itertools.product([5, 10, 15], [20, 30, 45, 60], [5, 8, 12]):
            rs = [evaluate(e, g, t_occ=to, t_vac=tv, t_unc=tu) for e, g in data.values()]
            rows.append((sum(r["f1"] for r in rs) / len(rs), sum(r["false_events"] + r["missed_events"] for r in rs), to, tv, tu))
        rows.sort(key=lambda r: (-r[0], r[1]))
        print("best settings on these (tuning) clips:  mean_F1, errors, T_occ, T_vac, T_unc")
        for r in rows[:5]: print("  %.3f  %d  %s %s %s" % r)
        return
    params = {k: v for k, v in dict(t_occ=a.t_occ, t_vac=a.t_vac, t_unc=a.t_unc, t_flick=a.t_flick).items() if v is not None}
    rows = []
    for c, (e, g) in data.items():
        r = evaluate(e, g, **params); r["clip"] = c; rows.append(r)
        print("clip %s: %s" % (c, {k: v for k, v in r.items() if k != "clip"}))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
