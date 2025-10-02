import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

API_ID = int(os.environ.get("TELEGRAM_API_ID") or 0)
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TELEGRAM_SESSION")
TRUECALLER_BOT = "TrueCaller1Bot"
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "20"))

if not (API_ID and API_HASH and STRING_SESSION):
    TELEGRAM_READY = False
else:
    TELEGRAM_READY = True
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

class LookupRequest(BaseModel):
    number: str

app = FastAPI(title="TrueCaller Query API")

# serve static files (frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

async def ensure_client_started():
    if not TELEGRAM_READY:
        raise RuntimeError("Telegram credentials/session missing.")
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session not authorized.")

def parse_truecaller_reply(text: str):
    out = {}
    s = text.replace("\r\n", "\n")
    m = re.search(r"Number:\s*([+\d\- ]+)", s)
    if m: out["number"] = m.group(1).strip()
    m = re.search(r"Country:\s*(.+)", s)
    if m: out["country"] = m.group(1).strip()
    m = re.search(r"TrueCaller Says:([\s\S]*?)(?:Unknown Says:|$)", s)
    if m:
        tc = m.group(1)
        name = re.search(r"Name:\s*(.+)", tc)
        carrier = re.search(r"Carrier:\s*(.+)", tc)
        if name: out.setdefault("truecaller", {})["name"] = name.group(1).strip()
        if carrier: out.setdefault("truecaller", {})["carrier"] = carrier.group(1).strip()
    m = re.search(r"Unknown Says:([\s\S]*?)(?:$)", s)
    if m:
        un = m.group(1)
        name = re.search(r"Name:\s*(.+)", un)
        email = re.search(r"Email:\s*([\w\.-]+@[\w\.-]+)", un)
        if name: out.setdefault("unknown", {})["name"] = name.group(1).strip()
        if email: out.setdefault("unknown", {})["email"] = email.group(1).strip()
    out["raw"] = text
    return out

@app.post("/lookup")
async def lookup(req: LookupRequest):
    if not TELEGRAM_READY:
        raise HTTPException(status_code=500, detail="Telegram not configured.")
    number = req.number.strip()
    if not re.match(r"^\+?\d{6,15}$", re.sub(r"[ \-()]", "", number)):
        raise HTTPException(status_code=400, detail="Invalid phone number format.")
    try:
        await ensure_client_started()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        async with client.conversation(TRUECALLER_BOT, timeout=TIMEOUT_SECONDS) as conv:
            await conv.send_message(number)
            resp = await conv.get_response()
            text = resp.text or ""
    except errors.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    parsed = parse_truecaller_reply(text)
    return {"ok": True, "data": parsed}

@app.get("/health")
async def health():
    return {"ok": True}
