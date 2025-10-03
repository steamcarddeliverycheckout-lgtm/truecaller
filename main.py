import os
import re
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient, errors, events
from telethon.sessions import StringSession

# ----------------------------
# Config (Render ENV)
# ----------------------------
API_ID = int(os.environ.get("TELEGRAM_API_ID") or 0)
API_HASH = os.environ.get("TELEGRAM_API_HASH")
STRING_SESSION = os.environ.get("TELEGRAM_SESSION")

# Target bot
TRUECALLER_BOT = "Truecaller_sbot"
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "20"))

# ----------------------------
# Telegram Client
# ----------------------------
if not (API_ID and API_HASH and STRING_SESSION):
    TELEGRAM_READY = False
    client = None
else:
    TELEGRAM_READY = True
    client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="Truecaller_sbot Proxy API")

class LookupRequest(BaseModel):
    number: str

async def ensure_client_started():
    if not TELEGRAM_READY:
        raise RuntimeError("Telegram credentials/session missing.")
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session not authorized. Recreate STRING_SESSION.")

# ----------------------------
# Parser for @Truecaller_sbot
# Example:
# ✅ Truecaller Details Revealed.!!
# ━━━━━━━━━━━━━━━━━━━━━━
# 📱  Carrier: Not Found
# 🌍 Country: Not Found
# 🌐 International Format: Not Found
# 📞 Local Format: Not Found
# 📍 Location: Not Found
# 🕒 Timezones: Not Found
# 🔍 Truecaller Name: usman pasha
# 👤 Username: No name found
# 🔎 Number search: 3
# ----------------------------
def parse_sbot_reply(text: str):
    s = text.replace("\r\n", "\n")
    out = {}

    def pick(pattern, cast=None):
        m = re.search(pattern, s, flags=re.IGNORECASE)
        if not m:
            return None
        val = m.group(1).strip()
        if cast:
            try:
                return cast(val)
            except Exception:
                return val
        return val

    out["carrier"] = pick(r"📱\s*Carrier:\s*(.+)")
    out["country"] = pick(r"🌍\s*Country:\s*(.+)")
    out["international_format"] = pick(r"🌐\s*International\s*Format:\s*(.+)")
    out["local_format"] = pick(r"📞\s*Local\s*Format:\s*(.+)")
    out["location"] = pick(r"📍\s*Location:\s*(.+)")
    out["timezones"] = pick(r"🕒\s*Timezones?:\s*(.+)")
    out["truecaller_name"] = pick(r"🔍\s*Truecaller\s*Name:\s*(.+)")
    out["username"] = pick(r"👤\s*Username:\s*(.+)")
    out["number_search"] = pick(r"🔎\s*Number\s*search:\s*(\d+)", cast=int)
    out["raw"] = text
    return out

# ----------------------------
# /lookup endpoint
# ----------------------------
@app.post("/lookup")
async def lookup(req: LookupRequest):
    if not TELEGRAM_READY:
        raise HTTPException(status_code=500, detail="Telegram not configured.")

    cleaned = re.sub(r"[ \-()]", "", req.number.strip())
    if not re.match(r"^\+?\d{6,15}$", cleaned):
        raise HTTPException(status_code=400, detail="Invalid phone number format.")

    try:
        await ensure_client_started()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Resolve bot entity (more robust)
        bot = await client.get_entity(TRUECALLER_BOT)

        # Send the number to the bot
        sent = await client.send_message(bot, req.number.strip())

        # Wait for first incoming message from that bot (correct method: wait_for)
        first_event = await client.wait_for(
            events.NewMessage(chats=bot, incoming=True),
            timeout=TIMEOUT_SECONDS,
        )

        texts = []
        t0 = getattr(first_event, "raw_text", None) or first_event.message.message or ""
        if t0:
            texts.append(t0)

        # Collect up to 2 quick follow-ups (bots sometimes split replies)
        for _ in range(2):
            try:
                ev = await client.wait_for(
                    events.NewMessage(chats=bot, incoming=True),
                    timeout=2
                )
                t = getattr(ev, "raw_text", None) or ev.message.message or ""
                if t:
                    texts.append(t)
            except asyncio.TimeoutError:
                break
            except Exception:
                break

        if not texts:
            raise HTTPException(status_code=502, detail="No reply text received from bot.")

        full_text = "\n\n".join(texts)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    except errors.FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram rate limit, wait {e.seconds}s")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram error: {e}")

    parsed = parse_sbot_reply(full_text)
    return {"ok": True, "data": parsed, "raw": full_text}

# ----------------------------
# Health
# ----------------------------
@app.get("/health")
async def health():
    return {"ok": True}

# ----------------------------
# Static frontend (mount LAST so /lookup isn't shadowed)
# ----------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
