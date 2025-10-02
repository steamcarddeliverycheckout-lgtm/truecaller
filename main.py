import os
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from fastapi.staticfiles import StaticFiles

# Env vars
API_ID = int(os.environ.get("TELEGRAM_API_ID") or 0)
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TELEGRAM_SESSION")
TRUECALLER_BOT = "TruecallerR0Bot"
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "20"))

if not (API_ID and API_HASH and STRING_SESSION):
    TELEGRAM_READY = False
else:
    TELEGRAM_READY = True
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

class LookupRequest(BaseModel):
    number: str

app = FastAPI(title="TrueCallerR0 Proxy")

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
    m = re.search(r"📞 Number:\s*([+\d\- ]+)", s)
    if m: out["number"] = m.group(1).strip()
    m = re.search(r"🌎 Country:\s*(.+)", s)
    if m: out["country"] = m.group(1).strip()
    if "💎 Paid sources data:" in s:
        out["paid"] = "Locked / Subscribe required"
    free_names = re.findall(r"👤 Name:\s*(.+)", s)
    if free_names:
        out["free_sources"] = free_names
    out["raw"] = text
    return out

# ✅ API pehle define karo
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
            responses = []
            for _ in range(3):
                try:
                    resp = await conv.get_response()
                    if resp.text:
                        responses.append(resp.text)
                except Exception:
                    break
            if not responses:
                raise HTTPException(status_code=502, detail="No reply from bot.")
            full_text = "\n\n".join(responses)
    except errors.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram error: {e}")

    parsed = parse_truecaller_reply(full_text)
    return {"ok": True, "data": parsed, "raw": full_text}

@app.get("/health")
async def health():
    return {"ok": True}

# ✅ Static serve last me rakho
app.mount("/", StaticFiles(directory="static", html=True), name="static")
