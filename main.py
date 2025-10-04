import os
import re
import json
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, List
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
TIMEOUT_SECONDS = int(os.environ.get("TIMEOUT_SECONDS", "14"))

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
    skip_keywords = [
        '🔄', 'Processing', '⚡',
        '𝗧𝗶𝗺𝗲:', 'Time:', 'Elapsed:',
        '𝗟𝗶𝗺𝗶𝘁:', 'Limit:',
        '𝗖𝗵𝗲𝗰𝗸𝗲𝗱 𝗯𝘆', 'Checked by', '@niggacheck_bot',
        'Gate:', 'User:'
    ]
    
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

def parse_card_parts(card: str):
    try:
        number, mm, yy_or_yyyy, cvv = [p.strip() for p in card.split("|")]
    except Exception:
        return None, None, None, None
    return number, mm, yy_or_yyyy, cvv

def year_variants(year: str) -> List[str]:
    y = year.strip()
    if len(y) == 4 and y.isdigit():
        return [y, y[-2:]]
    if len(y) == 2 and y.isdigit():
        return [y, f"20{y}"]
    return [y]

def month_variants(mm: str) -> List[str]:
    m = mm.strip()
    if not m.isdigit():
        return [m]
    m_int = str(int(m))  # strip leading zero
    m_pad = m_int.zfill(2)
    return [m_pad, m_int]

def message_matches_card(text: str, card: str) -> bool:
    """Heuristic: check if a reply text likely refers to the same card.
    Tries exact pipe format variations and also falls back to number presence.
    """
    if not text or not card:
        return False
    number, mm, yy_or_yyyy, cvv = parse_card_parts(card)
    if not number:
        return False
    candidates = set()
    year_opts = year_variants(yy_or_yyyy or "")
    month_opts = month_variants(mm or "")
    for m in month_opts:
        for y in year_opts:
            candidates.add(f"{number}|{m}|{y}|{cvv}")
    # Also consider number alone as a weak signal
    candidates.add(number)
    s = text
    return any(c and c in s for c in candidates)

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
# SSE: /cc-check-advanced/stream
# ----------------------------
@app.get("/cc-check-advanced/stream")
async def cc_check_advanced_stream(card: str, checker: str, gate_category: str, gate_provider: str):
    if not TELEGRAM_READY:
        raise HTTPException(status_code=500, detail="Telegram not configured.")

    # Validate card format (number|month|year|cvv)
    card_pattern = r"^\d{13,19}\|\d{2}\|\d{2,4}\|\d{3,4}$"
    if not re.match(card_pattern, card.strip()):
        raise HTTPException(status_code=400, detail="Invalid card format. Use: number|month|year|cvv")

    checker = checker.strip().lower()
    category = gate_category.strip().lower()
    provider = gate_provider.strip().lower()

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

    checker2_maps = {
        "auth": {
            "braintree": "/br",
            "stripe": "/chk",
        },
        "charge": {
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

    category_map = maps.get(category, {})
    cmd = category_map.get(provider)
    if not cmd:
        valid = ", ".join(category_map.keys()) or "none"
        raise HTTPException(status_code=400, detail=f"Invalid provider for {category}. Valid: {valid}")

    command = f"{cmd} {card.strip()}"

    async def event_gen() -> AsyncGenerator[str, None]:
        try:
            await ensure_client_started()
            bot = await client.get_entity(bot_username)

            seen_texts: set[str] = set()
            ordered_texts: list[str] = []
            final_sent = False

            # Initial notify
            init_payload = {"type": "status", "status": "sent", "command": command}
            yield f"event: update\n" + f"data: {json.dumps(init_payload)}\n\n"

            loop = asyncio.get_running_loop()
            async with client.conversation(bot, timeout=TIMEOUT_SECONDS + 30) as conv:
                await conv.send_message(command)

                # Phase 1: consume conversation queue quickly
                phase1_deadline = loop.time() + 18
                while loop.time() < phase1_deadline:
                    try:
                        msg = await asyncio.wait_for(conv.get_response(), timeout=4)
                        text = extract_message_text(msg)
                        if not text or text in seen_texts:
                            continue
                        seen_texts.add(text)
                        ordered_texts.append(text)

                        cleaned = clean_cc_response(text)
                        if cleaned.strip():
                            payload = {
                                "type": "update",
                                "raw": text,
                                "rawClean": cleaned,
                            }
                            yield f"event: update\n" + f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                        if is_final_cc_result(text):
                            final_payload = {
                                "type": "final",
                                "raw": text,
                                "rawClean": cleaned if cleaned.strip() else text,
                            }
                            yield f"event: final\n" + f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
                            final_sent = True
                            return
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

                # Phase 2: poll for edits/new messages in chat
                poll_deadline = loop.time() + 22
                while not final_sent and loop.time() < poll_deadline:
                    try:
                        async for m in client.iter_messages(bot, limit=10):
                            t = extract_message_text(m)
                            if not t or t in seen_texts:
                                continue
                            seen_texts.add(t)
                            ordered_texts.append(t)

                            cleaned2 = clean_cc_response(t)
                            if cleaned2.strip():
                                payload = {
                                    "type": "update",
                                    "raw": t,
                                    "rawClean": cleaned2,
                                }
                                yield f"event: update\n" + f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                            if is_final_cc_result(t):
                                final_payload = {
                                    "type": "final",
                                    "raw": t,
                                    "rawClean": cleaned2 if cleaned2.strip() else t,
                                }
                                yield f"event: final\n" + f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
                                final_sent = True
                                return
                        await asyncio.sleep(1)
                    except Exception:
                        await asyncio.sleep(1)

            # If we got here without final, emit best-effort last
            if not final_sent and ordered_texts:
                chosen = None
                for it in reversed(ordered_texts):
                    if not is_processing_message(it):
                        cleaned_final = clean_cc_response(it)
                        if cleaned_final.strip():
                            chosen = (it, cleaned_final)
                            break
                if not chosen:
                    it = ordered_texts[-1]
                    chosen = (it, clean_cc_response(it))
                final_payload = {
                    "type": "final",
                    "raw": chosen[0],
                    "rawClean": chosen[1] if chosen[1].strip() else chosen[0],
                }
                yield f"event: final\n" + f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_payload = {"type": "error", "detail": str(e)}
            yield f"event: error\n" + f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

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
        # Some bots edit their messages in-place, so we will poll the latest
        # messages from the bot dialog if needed to detect a final result.
        async with client.conversation(bot, timeout=TIMEOUT_SECONDS + 20) as conv:
            # Send the command to the bot
            await conv.send_message(command)
            
            all_messages = []
            final_text = ""
            
            # Phase 1: Wait up to 15s for a non-processing message via conversation queue
            phase1_deadline = asyncio.get_event_loop().time() + 15
            while asyncio.get_event_loop().time() < phase1_deadline:
                try:
                    msg = await asyncio.wait_for(conv.get_response(), timeout=3)
                    text = extract_message_text(getattr(msg, 'message', msg))
                    if text:
                        all_messages.append(text)
                        if is_final_cc_result(text):
                            final_text = text
                            break
                except asyncio.TimeoutError:
                    # keep trying in loop until deadline
                    continue
                except Exception:
                    break

            # Phase 2: If still not final, poll recent messages from the bot chat
            # Some bots edit messages or send outside the conversation queue
            if not final_text:
                poll_deadline = asyncio.get_event_loop().time() + 20
                while asyncio.get_event_loop().time() < poll_deadline:
                    try:
                        async for m in client.iter_messages(bot, limit=5):
                            t = extract_message_text(m)
                            if t and t not in all_messages:
                                all_messages.append(t)
                            if is_final_cc_result(t):
                                final_text = t
                                break
                        if final_text:
                            break
                        await asyncio.sleep(2)
                    except Exception:
                        await asyncio.sleep(2)

        if not all_messages:
            raise HTTPException(status_code=502, detail="No reply text received from bot.")

        if not final_text:
            # As a fallback, pick the last non-processing message if any
            for msg in reversed(all_messages):
                if not is_processing_message(msg):
                    final_text = msg
                    break
            if not final_text:
                final_text = all_messages[-1]
        
        # Clean the response - remove unwanted parts
        cleaned_text = clean_cc_response(final_text)
        
        return {"ok": True, "raw": cleaned_text, "full_response": final_text, "all_messages": len(all_messages)}

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
        cleaned, full, total = await perform_cc_check(bot_username=bot_username, command=command)
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
