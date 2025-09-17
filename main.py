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
if not base_url or not api_key:
    print("Some Environmental Variables are missing!")
    exit(1)
bot = WAHABot(base_url=base_url, api_key=api_key, session="default", webhook_func=webhook)

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

@bot.on_mention("admins")
@bot.on_mention("control")
async def on_mention_admins(client: WAHABot, chat_id: str, message_id: str, parsed, **kwargs) -> Dict[str, Any]:
    if not parsed.get("is_group"):
        print("No tags in private chats")
        return {"status": "ok"}

    messages = await get_mentions_list(
        client, chat_id, parsed.get("me", {}), admins_only=True
    )

    if not messages:
        return {"status": "empty"}

    return await bot.send(
        chat_id=chat_id,
        text=" | ".join(messages),
        reply_to=message_id,
    )

@bot.on_mention("all")
@bot.on_mention("everyone")
async def on_mention_all(client: WAHABot, chat_id: str, message_id: str, parsed, **kwargs) -> Dict[str, Any]:

    if not parsed.get("is_group"):
        print("No tags in private chats")
        return {"status": "ok"}

    messages = await get_mentions_list(client, chat_id, parsed.get("me", {}))

    if not messages:
        return {"status": "empty"}

    return await bot.send(
        chat_id=chat_id,
        text=" | ".join(messages),
        reply_to=message_id,
    )

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
    
    for command_func, command in commands:
        print(f"Registering {command} on {command_func.__name__}")
        decorated_func = listener_func(command)(command_func)
        globals()[command_func.__name__] = decorated_func

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(bot.app, host="0.0.0.0", port=int(run_port))
