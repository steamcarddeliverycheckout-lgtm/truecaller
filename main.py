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
SECOND_CC_BOT = "Jackthe_ripper_bot"
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

class AdvancedCCRequest(BaseModel):
    card: str
    checker: str  # 'first' or 'second'
    gate_category: str  # 'auth' | 'charge'
    gate_provider: str  # provider code per checker/category

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
# Parser for CC checker bot response
# ----------------------------
def clean_cc_response(text: str):
    """Extract only the important parts from CC checker response"""
    if not text:
        return ""
    
    lines = text.split('\n')
    important_lines = []
    
    # Skip lines to exclude
    skip_keywords = ['🔄', 'Processing', '⚡', '𝗧𝗶𝗺𝗲:', '𝗟𝗶𝗺𝗶𝘁:', '𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆', 'Checked by', '@niggacheck_bot']
    
    # Lines to keep
    keep_keywords = ['𝗖𝗮𝗿𝗱:', '𝐆𝐚𝐭𝐞𝐰𝐚𝐲:', '𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:', '𝗜𝗻𝗳𝗼:', '𝐈𝐬𝐬𝐮𝐞𝐫:', '𝐂𝐨𝐮𝐧𝐭𝐫𝐲:', 
                     'Card:', 'Gateway:', 'Response:', 'Info:', 'Issuer:', 'Country:',
                     'APPROVED', 'DECLINED', 'CHARGED', 'CVV', 'LIVE', 
                     '✅', '❌', '🌠', '💳', '🔥']
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
            
        # Skip unwanted lines
        if any(skip in line for skip in skip_keywords):
            continue
        
        # Keep important lines or lines with status indicators
        if any(keep in line for keep in keep_keywords):
            important_lines.append(line)
        # Also keep separator lines
        elif line.startswith('━'):
            important_lines.append(line)
    
    result = '\n'.join(important_lines)
    
    # If cleaning removed everything, return original
    return result if result else text

# ----------------------------
# Helpers for CC checker flow
# ----------------------------
def extract_message_text(msg):
    """Safely extract textual content from a Telethon Message (message or caption)."""
    if not msg:
        return ""
    return getattr(msg, "raw_text", None) or getattr(msg, "message", None) or getattr(msg, "text", None) or ""

def is_processing_message(text: str) -> bool:
    if not text:
        return False
    s = text.lower()
    return ("processing" in s) or ("🔄" in text) or ("loading" in s) or ("working" in s)

def is_final_cc_result(text: str) -> bool:
    """Heuristic to detect when a CC checker reply is a final result, not a progress update."""
    if not text:
        return False
    if is_processing_message(text):
        return False
    # Common indicators the result is finalized
    indicators_any = [
        "𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:", "Response:", "APPROVED", "DECLINED", "CHARGED",
        "𝗖𝗮𝗿𝗱:", "Card:", "𝐆𝐚𝐭𝐞𝐰𝐚𝐲:", "Gateway:",
        "Issuer:", "𝐈𝐬𝐬𝐮𝐞𝐫:", "Country:", "𝐂𝐨𝐮𝐧𝐭𝐫𝐲:", "CVV", "LIVE", "DEAD",
        "✅", "❌"
    ]
    return any(k in text for k in indicators_any)

async def perform_cc_check_realtime(bot_username: str, command: str, card_number: str):
    """
    Send a command to the bot and monitor messages in REAL-TIME using event handlers.
    Captures responses immediately as they appear, monitoring for card details.
    """
    await ensure_client_started()
    bot = await client.get_entity(bot_username)
    bot_id = bot.id

    # Extract just the card number (first part before |)
    card_prefix = card_number.split('|')[0] if '|' in card_number else card_number
    
    # Storage for captured messages
    collected_messages = []
    final_result = asyncio.Event()
    final_text = None
    
    async def message_handler(event):
        """Real-time message handler - captures messages as they arrive"""
        nonlocal final_text
        
        # Only process messages from our target bot
        if event.sender_id != bot_id:
            return
            
        text = extract_message_text(event.message)
        if not text:
            return
        
        # Check if message contains our card details
        if card_prefix in text or card_number in text:
            collected_messages.append(text)
            
            # If it's a final result, capture it and signal completion
            if is_final_cc_result(text):
                final_text = text
                final_result.set()
    
    # Register the event handler for new messages
    handler = client.add_event_handler(
        message_handler,
        events.NewMessage(chats=bot_id)
    )
    
    try:
        # Send the command
        await client.send_message(bot, command)
        
        # Wait for final result with timeout
        try:
            await asyncio.wait_for(final_result.wait(), timeout=TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            # If timeout, try to get the latest collected message
            if collected_messages:
                # Use the last non-processing message if available
                for text in reversed(collected_messages):
                    if not is_processing_message(text):
                        final_text = text
                        break
                if not final_text:
                    final_text = collected_messages[-1]
            else:
                # Fallback: try to get latest messages from chat
                async for m in client.iter_messages(bot, limit=5):
                    t = extract_message_text(m)
                    if t and (card_prefix in t or card_number in t):
                        collected_messages.append(t)
                        if is_final_cc_result(t):
                            final_text = t
                            break
                
                if not final_text and collected_messages:
                    final_text = collected_messages[-1]
    
    finally:
        # Always remove the event handler
        client.remove_event_handler(handler)
    
    if not final_text and not collected_messages:
        raise HTTPException(status_code=502, detail="No reply received from bot.")
    
    if not final_text:
        final_text = collected_messages[-1] if collected_messages else ""
    
    cleaned_text = clean_cc_response(final_text)
    return cleaned_text, final_text, len(collected_messages)

async def perform_cc_check(bot_username: str, command: str):
    """Send a command to the given bot and wait for a final response using robust strategy."""
    await ensure_client_started()
    bot = await client.get_entity(bot_username)

    collected: list[str] = []
    seen = set()

    def push(text: str):
        if text and text not in seen:
            collected.append(text)
            seen.add(text)

    final_text = ""
    loop = asyncio.get_running_loop()

    async with client.conversation(bot, timeout=TIMEOUT_SECONDS + 30) as conv:
        await conv.send_message(command)

        # Phase 1: conversation response queue (up to ~18s)
        phase1_deadline = loop.time() + 18
        while loop.time() < phase1_deadline:
            try:
                msg = await asyncio.wait_for(conv.get_response(), timeout=4)
                text = extract_message_text(msg)
                if text:
                    push(text)
                    if is_final_cc_result(text):
                        final_text = text
                        break
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

        # Phase 2: poll chat for edited/new messages (up to ~22s)
        if not final_text:
            poll_deadline = loop.time() + 22
            while loop.time() < poll_deadline:
                try:
                    async for m in client.iter_messages(bot, limit=10):
                        t = extract_message_text(m)
                        if t:
                            push(t)
                            if is_final_cc_result(t):
                                final_text = t
                                break
                    if final_text:
                        break
                    await asyncio.sleep(1)
                except Exception:
                    await asyncio.sleep(1)

    if not collected:
        raise HTTPException(status_code=502, detail="No reply text received from bot.")

    if not final_text:
        # fallback to the latest non-processing message if available
        for text in reversed(collected):
            if not is_processing_message(text):
                final_text = text
                break
        if not final_text:
            final_text = collected[-1]

    cleaned_text = clean_cc_response(final_text)
    return cleaned_text, final_text, len(collected)

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
        # Use REAL-TIME monitoring to capture responses immediately
        cleaned_text, full_response, total_messages = await perform_cc_check_realtime(
            bot_username=CC_CHECKER_BOT,
            command=command,
            card_number=req.card.strip()
        )
        
        return {"ok": True, "raw": cleaned_text, "full_response": full_response, "all_messages": total_messages}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout waiting for bot reply.")
    except errors.FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram rate limit, wait {e.seconds}s")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Telegram error: {e}")

# ----------------------------
# /cc-check-advanced endpoint (two checkers, selectable gates)
# ----------------------------
@app.post("/cc-check-advanced")
async def cc_check_advanced(req: AdvancedCCRequest):
    if not TELEGRAM_READY:
        raise HTTPException(status_code=500, detail="Telegram not configured.")

    # Validate card format (number|month|year|cvv)
    card_pattern = r"^\d{13,19}\|\d{2}\|\d{2,4}\|\d{3,4}$"
    if not re.match(card_pattern, req.card.strip()):
        raise HTTPException(status_code=400, detail="Invalid card format. Use: number|month|year|cvv")

    checker = req.checker.strip().lower()
    category = req.gate_category.strip().lower()
    provider = req.gate_provider.strip().lower()

    # Checker 1 (first): niggacheck_bot
    checker1_maps = {
        "auth": {
            "stripe": "/st",
            "braintree": "/ba",
        },
        "charge": {
            "paypal": "/pp",
            "shopify": "/sp",
        },
    }

    # Checker 2 (second): Jackthe_ripper_bot
    checker2_maps = {
        "auth": {
            # user-specified: braintree => /br, stripe => /chk
            "braintree": "/br",
            "stripe": "/chk",
        },
        "charge": {
            # user-specified: braintree => /ch, stripe => /sk
            "braintree": "/ch",
            "stripe": "/sk",
        },
    }

    if checker not in ("first", "second"):
        raise HTTPException(status_code=400, detail="checker must be 'first' or 'second'")
    if category not in ("auth", "charge"):
        raise HTTPException(status_code=400, detail="gate_category must be 'auth' or 'charge'")

    maps = checker1_maps if checker == "first" else checker2_maps
    bot_username = CC_CHECKER_BOT if checker == "first" else SECOND_CC_BOT

    # Provider mapping rules
    category_map = maps.get(category, {})
    cmd = category_map.get(provider)
    if not cmd:
        valid = ", ".join(category_map.keys()) or "none"
        raise HTTPException(status_code=400, detail=f"Invalid provider for {category}. Valid: {valid}")

    command = f"{cmd} {req.card.strip()}"

    try:
        # Use REAL-TIME monitoring to capture responses immediately
        cleaned, full, total = await perform_cc_check_realtime(
            bot_username=bot_username,
            command=command,
            card_number=req.card.strip()
        )
        return {"ok": True, "raw": cleaned, "full_response": full, "messages": total}
    except HTTPException:
        raise
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
