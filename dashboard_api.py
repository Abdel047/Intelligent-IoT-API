"""Dashboard med server-side API-adgang, sessionslogin og CSRF-kontrol."""
import asyncio
from collections import defaultdict, deque
import hashlib
import logging
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ASSETS = Path(__file__).resolve().parent / "dashboard"
COOKIE = "iot_dashboard_session"
SESSION_SECONDS = 4 * 60 * 60
logger = logging.getLogger("uvicorn.error")


class LoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=256)


def install_dashboard(app, reading_model, threshold):
    # Kun serverhukommelse. Sessions bliver ugyldige ved genstart.
    sessions = {}
    attempts = defaultdict(deque)
    global_attempts = deque()

    def prune():
        now = time.monotonic()
        for token in list(sessions):
            if sessions[token]["expires"] <= now:
                del sessions[token]
        for address in list(attempts):
            while attempts[address] and attempts[address][0] <= now - 60:
                attempts[address].popleft()
            if not attempts[address]:
                del attempts[address]
        while global_attempts and global_attempts[0] <= now - 60:
            global_attempts.popleft()

    def same_origin(request: Request):
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or parsed.netloc != request.headers.get("host"):
                raise HTTPException(403, "Anmodningen skal komme fra dashboardets egen adresse.")

    def session(request: Request):
        prune()
        token = request.cookies.get(COOKIE, "")
        record = sessions.get(hashlib.sha256(token.encode()).hexdigest()) if token else None
        if not record:
            raise HTTPException(401, "Log ind på dashboardet.")
        return record

    def write_session(request: Request, record=Depends(session)):
        same_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(supplied.encode(), record["csrf"].encode()):
            raise HTTPException(403, "Sikkerhedskontrollen fejlede. Genindlæs dashboardet.")
        return record

    @app.middleware("http")
    async def dashboard_headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/dashboard"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        return response

    @app.get("/dashboard", include_in_schema=False)
    @app.get("/dashboard/", include_in_schema=False)
    def page():
        return FileResponse(ASSETS / "index.html")

    @app.post("/dashboard/login", include_in_schema=False)
    async def login(data: LoginInput, request: Request):
        same_origin(request)
        password = os.getenv("DASHBOARD_PASSWORD", "")
        if len(password) < 16:
            raise HTTPException(503, "Dashboard-login mangler. Kør scripts/prepare_env.py og genstart API'et.")
        prune()
        address = request.client.host if request.client else "unknown"
        if len(attempts[address]) >= 5 or len(global_attempts) >= 50:
            raise HTTPException(429, "For mange loginforsøg. Vent ét minut.", headers={"Retry-After": "60"})
        if not secrets.compare_digest(hashlib.sha256(data.password.encode()).digest(), hashlib.sha256(password.encode()).digest()):
            now = time.monotonic()
            attempts[address].append(now)
            global_attempts.append(now)
            raise HTTPException(401, "Forkert adgangskode.")
        if len(sessions) >= 100:
            raise HTTPException(429, "For mange aktive sessioner. Prøv senere.")
        previous = request.cookies.get(COOKIE)
        if previous:
            sessions.pop(hashlib.sha256(previous.encode()).hexdigest(), None)
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(token.encode()).hexdigest()] = {"expires": time.monotonic() + SESSION_SECONDS, "csrf": csrf}
        response = JSONResponse({"authenticated": True, "csrf_token": csrf})
        # Lokalt HTTP tillades på localhost; gatewayens HTTPS giver Secure-cookie.
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(COOKIE, token, httponly=True, secure=secure, samesite="strict", max_age=SESSION_SECONDS, path="/dashboard")
        logger.info("Dashboard-login oprettet.")
        return response

    @app.get("/dashboard/session", include_in_schema=False)
    def current_session(record=Depends(session)):
        return {"authenticated": True, "csrf_token": record["csrf"]}

    @app.post("/dashboard/logout", include_in_schema=False)
    def logout(request: Request, record=Depends(write_session)):
        token = request.cookies.get(COOKIE, "")
        sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/dashboard")
        return response

    async def api_call(request, method, path, data=None):
        # Fast endpointliste og intern ASGI-transport: ingen fri proxy/SSRF.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app), base_url="http://internal") as client:
            return await client.request(method, path, json=data, headers={"X-API-Key": request.app.state.api_key})

    @app.get("/dashboard/data", include_in_schema=False)
    async def snapshot(request: Request, record=Depends(session)):
        health = await api_call(request, "GET", "/health")
        result = {"api_status": "online", "database_status": "connected" if health.status_code == 200 else "disconnected",
                  "threshold": threshold, "readings": [], "events": [], "alarms": [],
                  "docker": {name: "unavailable" for name in ("api", "mysql", "gateway")},
                  "docker_note": "Containerstatus er ikke tilgængelig uden Docker-adgang. API/database-health er målt separat.",
                  "updated_at": time.time(), "errors": []}
        if health.status_code == 200:
            responses = await asyncio.gather(*(api_call(request, "GET", path) for path in ("/readings", "/events", "/alarms?status=all")))
            for name, response in zip(("readings", "events", "alarms"), responses):
                if response.status_code == 200:
                    result[name] = response.json()
                else:
                    result["errors"].append("Kunne ikke hente " + name + ".")
        return result

    @app.post("/dashboard/readings", include_in_schema=False)
    async def submit_reading(reading: reading_model, request: Request, record=Depends(write_session)):
        response = await api_call(request, "POST", "/readings", reading.model_dump())
        return JSONResponse(response.json(), status_code=response.status_code)

    @app.patch("/dashboard/alarms/{alarm_id}/acknowledge", include_in_schema=False)
    async def acknowledge(alarm_id: int, request: Request, record=Depends(write_session)):
        response = await api_call(request, "PATCH", f"/alarms/{alarm_id}/acknowledge")
        return JSONResponse(response.json(), status_code=response.status_code)

    app.mount("/dashboard/assets", StaticFiles(directory=ASSETS), name="dashboard-assets")
