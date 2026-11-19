"""FastAPI web layer. Run from the project root:  uvicorn backend.main:app --reload --port 8000"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import List, Optional
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.db import make_store
from backend.service import Service

app = FastAPI(title="Restaurant Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
svc = Service(make_store())


class Login(BaseModel):
    username: str
    password: str


class Evidence(BaseModel):
    table_id: str
    evidence: str
    ts: float
    people: int = 0


class SetState(BaseModel):
    state: str


class Zone(BaseModel):
    table_id: str
    polygon: List[List[float]]


class Settings(BaseModel):
    retention_days: Optional[int] = None
    camera_name: Optional[str] = None


def current_user(authorization: str = Header(default="")):
    u = svc.user(authorization.replace("Bearer ", ""))
    if not u:
        raise HTTPException(401, "please log in")
    return u


def manager_only(u=Depends(current_user)):
    if u["role"] != "manager":
        raise HTTPException(403, "manager only")
    return u


@app.get("/api/health")
def health():
    return {"ok": True, "store": svc.store.kind}


@app.post("/api/login")
def login(b: Login):
    try:
        token, role = svc.login(b.username, b.password)
    except ValueError as e:
        raise HTTPException(401, str(e))
    return {"token": token, "role": role, "name": b.username}


@app.post("/api/evidence")                       # called by vision/pipeline.py (no login: local machine)
def evidence(b: Evidence):
    try:
        svc.evidence(b.table_id, b.evidence, b.ts, b.people)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/tables")
def tables(u=Depends(current_user)):
    return svc.tables_view()


def _act(fn, *a):
    try:
        fn(*a)
    except KeyError:
        raise HTTPException(404, "unknown table")
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/tables/{tid}/cleaning")
def cleaning(tid: str, u=Depends(current_user)):
    return _act(svc.cleaning, tid, u["name"])


@app.post("/api/tables/{tid}/ready")
def ready(tid: str, u=Depends(current_user)):
    return _act(svc.ready, tid, u["name"])


@app.post("/api/tables/{tid}/set")
def set_state(tid: str, b: SetState, u=Depends(current_user)):
    return _act(svc.set_state, tid, b.state, u["name"])


@app.post("/api/zones")
def zones_post(b: Zone):
    svc.set_zone(b.table_id, b.polygon); return {"ok": True}


@app.get("/api/zones")
def zones_get(u=Depends(current_user)):
    return svc.zones()


@app.get("/api/sessions")
def sessions(u=Depends(current_user)):
    return svc.sessions()


@app.get("/api/analytics")
def analytics(u=Depends(current_user)):
    return svc.analytics()


@app.get("/api/settings")
def get_settings(u=Depends(manager_only)):
    return svc.settings()


@app.put("/api/settings")
def put_settings(b: Settings, u=Depends(manager_only)):
    try:
        return svc.update_settings(b.retention_days, b.camera_name)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/admin/purge")
def purge(u=Depends(manager_only)):
    return svc.purge()
