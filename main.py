import os
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from src.custom_client import WAHABot
from src.webhook import webhook

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    ...

base_url = os.getenv("BOT_URL")
api_key = os.getenv("BOT_API_KEY")
run_port = os.getenv("WEBHOOK_PORT", 8000)
if not base_url or not api_key:
    print("Some Environmental Variables are missing!")
    exit(1)
bot = WAHABot(base_url=base_url, api_key=api_key, session="default", webhook_func=webhook)


@bot.on("pull")
async def on_pull(
    client: WAHABot, chat_id: str, message_id: str, args: List[str],
    raw: Dict[str, Any], **kwargs
) -> Dict[str, Any]:
    # Accepts:
    #   "pull"
    #   "@<my_number> pull"
    #   "pull @<my_number>."
    #   "pull 3133455"
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

@bot.app.route("/send", methods=["POST"])
async def send_message(request: Request):
    body = await request.json()
    chat_id = body.get("chat_id")
    message = body.get("text")
    if not chat_id or not message:
        return JSONResponse({"error": "`chat_id` and `text` are both required and cannot be empty"}, 400)
    
    resp = await bot.send(chat_id=chat_id, text=message)
    return JSONResponse(resp)

# --------------- Runnable server loop ---------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(bot.app, host="0.0.0.0", port=int(run_port))
