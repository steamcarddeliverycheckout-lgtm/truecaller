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

# Target bots
TRUECALLER_BOT = "Truecaller_sbot"
CC_CHECKER_BOT = "niggacheck_bot"
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

class CCCheckRequest(BaseModel):
    card: str
    gate_type: str  # 'stripe', 'braintree', 'paypal', 'shopify'

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

        # Use conversation to wait for bot replies
        async with client.conversation(bot, timeout=TIMEOUT_SECONDS) as conv:
            # Send the number to the bot
            await conv.send_message(req.number.strip())
            
            # Get the first reply
            response = await conv.get_response()
            
            texts = []
            if response.text:
                texts.append(response.text)
            
            # Collect up to 2 quick follow-ups (bots sometimes split replies)
            for _ in range(2):
                try:
                    msg = await asyncio.wait_for(conv.get_response(), timeout=2)
                    if msg.text:
                        texts.append(msg.text)
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
# /cc-check endpoint
# ----------------------------
@app.post("/cc-check")
async def cc_check(req: CCCheckRequest):
    if not TELEGRAM_READY:
        raise HTTPException(status_code=500, detail="Telegram not configured.")

    # Validate card format (number|month|year|cvv)
    card_pattern = r"^\d{13,19}\|\d{2}\|\d{2,4}\|\d{3,4}$"
    if not re.match(card_pattern, req.card.strip()):
        raise HTTPException(status_code=400, detail="Invalid card format. Use: number|month|year|cvv")

    # Map gate type to command
    gate_commands = {
        "stripe": "/st",
        "braintree": "/ba",
        "paypal": "/pp",
        "shopify": "/sp"
    }
    
    if req.gate_type not in gate_commands:
        raise HTTPException(status_code=400, detail="Invalid gate type. Use: stripe, braintree, paypal, or shopify")
    
    command = f"{gate_commands[req.gate_type]} {req.card.strip()}"

    try:
        await ensure_client_started()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        # Resolve bot entity
        bot = await client.get_entity(CC_CHECKER_BOT)

        # Use conversation to wait for bot replies
        async with client.conversation(bot, timeout=TIMEOUT_SECONDS) as conv:
            # Send the command to the bot
            await conv.send_message(command)
            
            # Get the first reply
            response = await conv.get_response()
            
            texts = []
            if response.text:
                texts.append(response.text)
            
            # Collect up to 3 quick follow-ups (bot might send multiple messages)
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(conv.get_response(), timeout=3)
                    if msg.text:
                        texts.append(msg.text)
                except asyncio.TimeoutError:
                    break
                except Exception:
                    break

        if not texts:
            raise HTTPException(status_code=502, detail="No reply text received from bot.")

        full_text = "\n\n".join(texts)
        
        return {"ok": True, "raw": full_text}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    except errors.FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram rate limit, wait {e.seconds}s")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram error: {e}")

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
