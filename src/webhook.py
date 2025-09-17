import re
import string
from typing import List, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse

from src.custom_client import WAHABot

_PUNCT_EXCEPT_AT = "".join(ch for ch in string.punctuation if ch != "@")
_MENTIONS_RE = re.compile(r"(?:@\d+@c\.us|@(all|everyone)\b)")

def clean_token(tok: str) -> str:
    tok = tok.strip()
    return tok.translate(str.maketrans("", "", _PUNCT_EXCEPT_AT))

def normalize(tok: str) -> str:
    return tok.strip().lower()

def is_mention(tok: str) -> bool:
    return bool(_MENTIONS_RE.match(tok))

def parse_command(text: str) -> Tuple[str, List[str], List[str]]:
    # Ignore leading mentions, strip punctuation/spaces, support args
    raw = [t for t in text.split() if t.strip()]
    cleaned = [clean_token(t) for t in raw]
    mentions = []
    new_text = []
    for token in cleaned:
        if is_mention(token):
            if token.count("@") == 2:
                token = token.rsplit("@", 1)[0]
            mentions.append(token.strip("@"))
        else:
            new_text.append(token)
   
    if new_text:
        cmd, *args = new_text
    elif not mentions:
        return "", [], []
    else:
        cmd, *args = ""

    return cmd, list(args), list(dict.fromkeys(mentions))

def parse_message_type(event: dict):
    # TODO: Return if mentioning me or not for commands or responses
    event_type = event.get("event")
    if not event_type:
        print("No event")
        return {}

    if event_type == "session.status":
        status = event.get("payload", {}).get("status")
        if not status:
            print("Invalid Status")
            return {}
        print(f"Session", status)
        return {
            "type": "session",
            "mode": status,  # starting, scan_qr_code, working, stopped - all uppercase
        }

    if event_type in ["message"]:  # message.* also uses same dict
        payload = event.get("payload", {})
        message_id = payload.get("id")
        chat_id: str = payload.get("from")

        me = event.get("me", {})
        my_id = me.get("id")

        my_label_raw = me.get("lid")
        if my_label_raw:
            _l_i, _l_r = my_label_raw.split("@", 1)
            _l_i = _l_i.split(":", 1)[0]
            my_label = f"{_l_i.strip()}@{_l_r.strip()}"
        else:
            my_label = ""

        if not my_id or not my_label or not payload:
            print("Message received but my info is invalid!")
            return {
                "chat_id": chat_id,
                "reply_id": message_id,
                "should_reply": False,
            }

        engine_data = payload.get("_data", {})

        if engine_data.get("status") == "DELIVERY_ACK":
            print("Message type is DELIVERY_ACK so skip")
            return {}

        reply_id: str = message_id
        chat_type = chat_id.rsplit("@", 1)[-1].strip()[0].lower()

        from_me = False
        if chat_id == my_id:
            from_me = True
        elif engine_data.get("key", {}).get("senderLid") == my_label:
            from_me = True
        elif engine_data.get("key", {}).get("participant") == my_label:
            from_me = True
        elif str(payload.get("fromMe", "")).lower() == "true":
            from_me = True
        elif engine_data.get("key", {}).get(
            "participantPn"
        ):  # This line is kept for clarity, not needed
            from_me = False  # If not me then it has participant pn

        if from_me:
            print(f"Skipping message from me in {chat_type}")
            return {}

        message: str = payload.get("body", "")
        if not message.strip():
            print(f"Received message in {chat_type} with no body")
            return {
                "chat_id": chat_id,
                "reply_id": message_id,
                "should_reply": False,
            }

        if chat_type == "g":  # group
            if chat_id != payload.get("to"):  # duplicate message, unsure why!
                print(f"Received duplicate message in {chat_type}, unsure how to parse")
                return {}
            sender_id = (
                engine_data.get("key", {}).get("participantPn", "").split("@", 1)[0]
                + "@c.us"
            )
            sender_label = payload.get("participant")
        else:
            sender_id = chat_id
            sender_label = engine_data.get("key", {}).get("senderLid")

        print(f"Received message in {chat_type} from {sender_id} - {sender_label}")
        return {
            "is_group": chat_type == "g",
            "is_chat": chat_type == "c",
            "sender": sender_id,
            "sender_label": sender_label,
            "chat_id": chat_id,
            "reply_id": reply_id,
            "should_reply": True,
            "text": message,
            "me": {
                "id": my_id,
                "label": my_label
            }
        }
    else:
        raise NotImplementedError(f"{event_type=} is not yet supported!")

async def webhook(client: WAHABot, request: Request) -> JSONResponse:
    evt = await request.json()
    if evt.get("event") in client.IGNORE_MESSAGES_SET:
        return JSONResponse({"status": "ignored"})

    parsed_message = parse_message_type(event=evt)  # TODO: Detect also if this is a mention to me
    print(f"Parsed event: {parsed_message}")
    text = parsed_message.get("text", "") # should not be possible cuz empty text is always should_reply = False
    chat_id = parsed_message.get("chat_id")
    reply_id = parsed_message.get("reply_id")
    should_reply = parsed_message.get("should_reply", False)
    if reply_id and chat_id:
        print(f"Setting {chat_id} seen marker to {reply_id}")
        client.MESSAGES_HISTORY[chat_id] = reply_id
    if not should_reply:
        return JSONResponse({"ok": False})
    

    cmd, args, mentions = parse_command(text)
    handler = client._handlers.get(cmd)
    mentions_handlers = []
    for mention in mentions:
        m_h = client._mentions_handlers.get(mention)
        if m_h:
            mentions_handlers.append(m_h)
    
    handlers = [handler] if handler else []
    handlers += mentions_handlers
    if not handlers:
        if mentions:
            print(f"Mentions was not a command")
        elif cmd:
            print(f"Command {cmd} has no handler")
        else:
            print(f"No command specified")
        return JSONResponse({"ok": False})
    
    for handler in handlers:
        result = await handler(
            client,
            chat_id=chat_id,
            message_id=reply_id,
            args=args,
            mentions=mentions,
            raw=evt,
            parsed=parsed_message,
        )
    return JSONResponse(result or {"ok": True})
