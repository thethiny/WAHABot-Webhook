import re
import string
from typing import List, Optional, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse

from src.custom_client import WAHABot
from src.utils import cleanup_label, is_mention, is_mentioned, is_me, is_target

_PUNCT_EXCEPT_AT = "".join(ch for ch in string.punctuation if ch != "@")
# _MENTIONS_RE = re.compile(r"(?:@\d+@c\.us|@(all|everyone)\b)") # TODO: Remove @ all/everyone and instead change the command from on_mention to on # TODO 2: Update the function to use the better METIONS_RE

def clean_token(tok: str) -> str:
    tok = tok.strip()
    return tok.translate(str.maketrans("", "", _PUNCT_EXCEPT_AT))

def normalize(tok: str) -> str:
    return tok.strip().lower()

# def is_mention(tok: str) -> bool:
#     return bool(_MENTIONS_RE.match(tok))

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
        cmd, *args = "",

    return cmd, list(args), list(dict.fromkeys(mentions))

def make_reply_id(message_id: str, chat_id: str, participant: str, is_sender_me: Optional[bool] = None, me: dict = {}):
    is_sender_me = is_sender_me if is_sender_me is not None else is_me(participant, me)
    
    reply_id = f"{str(is_sender_me).lower()}_{chat_id}_{message_id}_{participant}"
    
    return reply_id


def parse_message_event(event: dict):
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
        my_jid = me.get("jid")

        my_label = cleanup_label(me.get("lid"))

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

        message_stickers = engine_data.get("message", {}).get("stickerMessage", {})
        if message_stickers:
            sticker_hash = message_stickers.get("fileSha256", "")
            sticker_key = message_stickers.get("mediaKey", "")
            sticker_data = {
                "hash": sticker_hash,
                "key": sticker_key,
            }
        else:
            sticker_data = {}

        message: str = payload.get("body") or "" # may be None 
        if not message.strip():
            print(f"Received message in {chat_type} with no body")
            return {
                "chat_id": chat_id,
                "reply_id": message_id,
                "should_reply": False,
                "media": {
                    "sticker": sticker_data,
                }
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

        mentions_me = is_mentioned(message, me)
        reply_to = payload.get("replyTo") or {}
        reply_to_participant = reply_to.get("participant")
        reply_to_me = is_target(reply_to_participant, my_id, my_jid, my_label)
        reply_to_body = reply_to.get("body")

        reply_to_id = None
        if reply_to:
            reply_mid = reply_to.get("id", "")
            reply_part = reply_to.get("participant", "")
            reply_to_id = make_reply_id(reply_mid, chat_id, reply_part, is_target(reply_part, my_id, my_jid, my_label))

        return {
            "is_group": chat_type == "g",
            "is_chat": chat_type == "c",
            "sender": sender_id,
            "sender_label": sender_label,
            "chat_id": chat_id,
            "reply_id": reply_id,
            "should_reply": True,
            "text": message,
            "is_mentioned": mentions_me,
            "is_reply": reply_to_me,
            "reply_history": reply_to_body,
            "reply_history_id": reply_to_id,
            "me": {
                "id": my_id,
                "jid": my_jid,
                "lid": my_label
            },
            "media": {
                "sticker": sticker_data
            }
        }
    else:
        raise NotImplementedError(f"{event_type=} is not yet supported!")

async def webhook(client: WAHABot, request: Request) -> JSONResponse:
    evt = await request.json()
    if evt.get("event") in client.IGNORE_MESSAGES_SET:
        return JSONResponse({"status": "ignored"})

    parsed_message = parse_message_event(event=evt)
    print(f"Parsed event: {parsed_message}")
    text = parsed_message.get("text", "") # should not be possible cuz empty text is always should_reply = False
    chat_id = parsed_message.get("chat_id")
    reply_id = parsed_message.get("reply_id")
    should_reply = parsed_message.get("should_reply", False)
    mentions_me = parsed_message.get("is_mentioned", False)
    media = parsed_message.get("media", {})
    if reply_id and chat_id: # Reply id is simply message_id
        try:
            await client.mark_seen(chat_id, reply_id)
        except Exception:
            pass
    # if reply_id and chat_id:
    #     print(f"Setting {chat_id} seen marker to {reply_id}")
    #     client.MESSAGES_HISTORY.setdefault(chat_id, []).append(reply_id)
    #     if len(client.MESSAGES_HISTORY[chat_id]) > 10:
    #         try:
    #             await client.mark_chat_as_seen(chat_id)
    #         except Exception:
    #             pass
    if parsed_message.get("type") == "session":
        if client.admins:
            status = parsed_message.get("mode")
            for admin in client.admins:
                send_to = admin
                if '@' not in send_to:
                    send_to = admin.strip("+").strip() + "@c.us"
                else:
                    send_to = send_to.strip()
                try:
                    await client.send(send_to, f"Whatsapp Bot Status: {status}")
                except Exception as e:
                    print(f"Failed to notify admin {admin} for {e}")
                    continue
        for handler in client._status_handlers:
            handler(
                client=client,
                status=status,
                raw=evt,
                parsed=parsed_message,
            )

    if media:
        sticker = media.get("sticker", {})
        sticker_key = sticker.get("key")
        sticker_hash = sticker.get("hash")
        
        stickers_dict = client._media_handlers["stickers"]

        handler_key = ""
        if sticker_key in stickers_dict:
            handler_key = sticker_key
        elif sticker_hash in stickers_dict:
            handler_key = sticker_hash
        elif sticker_key:
            handler_key = "all"  # Allow handlers to register to all
        elif sticker_hash:
            handler_key = "all"

        handler = stickers_dict.get(handler_key)  # disallow "" key
        print(f"Handling sticker media {handler_key} with handler {handler}")
        if handler:
            try:
                await handler(
                    client=client,
                    chat_id=chat_id,
                    message_id=reply_id,
                    media=media,
                    raw=evt,
                    parsed=parsed_message,
                )
            except Exception as e:
                print(f"{handler=} failed with {e}")

    if not should_reply:
        return JSONResponse({"ok": False})

    cmd, args, mentions = parse_command(text)
    handler = client._handlers.get(cmd.lower())
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
        # else:
        # print(f"No command specified")

        if mentions_me: # If no command but is mentioned then call mentions handler
            print("Switching to mentions handler")
            all_handlers = client._mention_no_cmd_handlers
        else:
            print("Switching to fallback handler")
            all_handlers = client._no_cmd_handlers

        for handler in all_handlers:
            try:
                await handler(
                    client=client,
                    chat_id=chat_id,
                    message_id=reply_id,
                    args=args,
                    mentions=mentions,
                    media=media,
                    raw=evt,
                    parsed=parsed_message,
                )
            except Exception as e:
                print(f"{handler=} failed with {e}")

        return JSONResponse({"ok": bool(len(all_handlers)), "amount": len(all_handlers), "mention": mentions_me})

    for handler in handlers:
        result = await handler(
            client=client,
            chat_id=chat_id,
            message_id=reply_id,
            args=args,
            mentions=mentions,
            media=media,
            raw=evt,
            parsed=parsed_message,
        )
    return JSONResponse(result or {"ok": True})
