from functools import wraps
import os
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from src.custom_client import WAHABot
from src.webhook import webhook
from src.utils import get_mentions_list

try:
    from commands.custom_commands import custom_commands_registry
except ImportError:
    custom_commands_registry = {}

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    ...

def require_auth(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        req_api_key = request.headers.get("x-api-key")
        if req_api_key != api_key:
            return JSONResponse({"error", "Unauthorized"}, status_code=401)
        return await func(request, *args, **kwargs)
    return wrapper

base_url = os.getenv("BOT_URL")
api_key = os.getenv("BOT_API_KEY")
run_port = os.getenv("WEBHOOK_PORT", 8000)
notifs_admins = [a.strip() for a in os.getenv("NOTIFS_ADMINS", "").split(",") if a.strip()]
if not base_url or not api_key:
    print("Some Environmental Variables are missing!")
    exit(1)
bot = WAHABot(base_url=base_url, api_key=api_key, session="default", webhook_func=webhook, notifs_admins=notifs_admins)

@bot.on("pull")
async def on_pull(chat_id: str, message_id: str, args: List[str], **kwargs) -> Dict[str, Any]:
    if args and args[0]:
        return await bot.send(
            chat_id=chat_id,
            text=f"Pulling event {args[0]}",
            reply_to=message_id,
        )
    return await bot.send(
        chat_id=chat_id,
        text="Pulling latest events...",
        reply_to=message_id,
    )

async def on_mentions_handler(client: WAHABot, chat_id: str, message_id: str, parsed, args, admins_only, **kwargs) -> Dict[str, Any]:
    if not parsed.get("is_group"):
        print("No tags in private chats")
        return {"status": "ok"}

    messages = await get_mentions_list(client, chat_id, parsed.get("me", {}), admins_only=admins_only)

    if not messages:
        return {"status": "empty"}

    message = " ".join(args)

    text = message + "\n" if message else ""
    text += " | ".join(messages)

    reply_history_id = parsed.get("reply_history_id")
    if reply_history_id:
        reply_to = reply_history_id
    else:
        reply_to = message_id

    return await bot.send(
        chat_id=chat_id,
        text=text,
        reply_to=reply_to,
    )

@bot.on("@admin")
@bot.on("@admins")
@bot.on("@control")
async def on_mention_admins(client: WAHABot, chat_id: str, message_id: str, parsed, args, **kwargs) -> Dict[str, Any]:
    return await on_mentions_handler(client, chat_id, message_id, parsed, args, admins_only=True, **kwargs)


@bot.on("@all")
@bot.on("@everyone")
async def on_mention_all(client: WAHABot, chat_id: str, message_id: str, parsed, args, **kwargs) -> Dict[str, Any]:
    return await on_mentions_handler(client, chat_id, message_id, parsed, args, admins_only=False, **kwargs)

@bot.app.route("/send", methods=["POST"])
@require_auth
async def send_message(request: Request):
    body = await request.json()
    chat_id = body.get("chat_id")
    message = body.get("text")
    if not chat_id or not message:
        return JSONResponse({"error": "`chat_id` and `text` are both required and cannot be empty"}, 400)

    resp = await bot.send(chat_id=chat_id, text=message)
    return JSONResponse(resp)

@bot.app.get("/healthcheck")
async def healthcheck():
    return {"status": "ok"}


print("Registering Additional Commands")
for listener, commands in custom_commands_registry.items():
    listener_func = getattr(bot, listener)

    for cmd_var in commands:
        if isinstance(cmd_var, tuple):
            command_func, *command = cmd_var
            print(f"Registering {command} on {command_func.__name__} as {listener}")
        else:
            command_func = cmd_var
            command = []
            print(f"Registering {command_func.__name__} as {listener}")
        decorated_func = listener_func(*command)(command_func)
        globals()[command_func.__name__] = decorated_func

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(bot.app, host="0.0.0.0", port=int(run_port))
