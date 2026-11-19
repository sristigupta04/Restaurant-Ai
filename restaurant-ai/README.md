# AI Restaurant Intelligence System - starter kit

## Folders
- core/state_machine.py   the table states and rules (tested)
- backend/                FastAPI + storage (MongoDB or JSON file) + analytics + purge
- vision/                 zone_editor.py, pipeline.py (YOLO+ByteTrack), eval.py, zone_tools.py
- dashboard/src/App.jsx   React dashboard (copy into your Vite app)
- data/                   clips, zones.json, evidence, ground_truth (never upload to GitHub)

## Install
    python -m venv venv
    venv\Scripts\activate            (Windows)   or   source venv/bin/activate
    pip install -r requirements.txt

## Run the tests (no camera, no internet needed)
    python core/tests/test_state_machine.py
    python backend/test_service.py
    python vision/test_zone_tools.py
    python vision/test_eval.py

## Run the system
1. Backend (from the project root):   uvicorn backend.main:app --reload --port 8000
   Check http://localhost:8000/docs   Default logins: staff/staff123, manager/manager123 (CHANGE before demo day if you want)
2. Dashboard:   npm create vite@latest dashboard-app -- --template react ; cd dashboard-app ; npm install recharts
   copy dashboard/src/App.jsx over dashboard-app/src/App.jsx ; npm run dev      (http://localhost:5173)
3. Zones:       python vision/zone_editor.py --clip data/clips/calibration.mp4 --tables T1 T2 T3
4. Pipeline:    python vision/pipeline.py --clip data/clips/clip07.mp4 --start "2026-11-20 09:00:00" --api http://localhost:8000 --realtime --show
5. Evidence for evaluation (no API):  python vision/pipeline.py --clip data/clips/clip03.mp4 --out data/evidence/clip03.jsonl
6. Evaluate:    python vision/eval.py --clips 03 05 --csv results.csv

## Time
The pipeline sends video time added to --start. Staff button presses use the latest video time seen, so replays stay consistent.
