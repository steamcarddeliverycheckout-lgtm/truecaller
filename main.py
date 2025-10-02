import os
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from fastapi.staticfiles import StaticFiles

# --- Config from Render ENV ---
API_ID = int(os.environ.get("TELEGRAM_API_ID") or 0)
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TELEGRAM_SESSION")
TRUECALLER_BOT = "TruecallerR0Bot"   # ✅ new bot
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "20"))

# --- Setup Telegram Client ---
if not (API_ID and API_HASH and STRING_SESSION):
    TELEGRAM_READY = False
else:
    TELEGRAM_READY = True
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# --- FastAPI app ---
app = FastAPI(title="TrueCallerR0Bot Proxy API")

class LookupRequest(BaseModel):
    number: str

# --- Ensure Telegram client connected ---
async def ensure_client_started():
    if not TELEGRAM_READY:
        raise RuntimeError("Telegram credentials/session missing.")
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session not authorized.")

# --- Parser for Bot Reply ---
def parse_truecaller_reply(text: str):
    out = {}
    s = text.replace("\r\n", "\n")

    # Number
    m = re.search(r"📞 Number:\s*([+\d\- ]+)", s)
    if m:
        out["number"] = m.group(1).strip()

    # Country
    m = re.search(r"🌎 Country:\s*(.+)", s)
    if m:
        out["country"] = m.group(1).strip()

    # Paid sources
    if "💎 Paid sources data:" in s:
        out["paid"] = "Locked / Subscribe required"

    # Free sources (multiple names)
    free_names = re.findall(r"👤 Name:\s*(.+)", s)
    if free_names:
        out["free_sources"] = free_names

    out["raw"] = text
    return out

# --- Lookup API ---
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
        # ✅ send number to bot
        await client.send_message(TRUECALLER_BOT, number)

        # ✅ wait for bot's reply (not own message)
        resp = await client.wait_for_message(from_user=TRUECALLER_BOT, timeout=TIMEOUT_SECONDS)

        if not resp or not resp.text:
            raise HTTPException(status_code=502, detail="Bot reply empty")

        full_text = resp.text
    except errors.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram error: {e}")

    parsed = parse_truecaller_reply(full_text)
    return {"ok": True, "data": parsed, "raw": full_text}

# --- Health check ---
@app.get("/health")
async def health():
    return {"ok": True}

# --- Serve frontend ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")
