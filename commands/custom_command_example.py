from typing import Any, Dict
from src.custom_client import WAHABot
from src.utils import get_mentions_list


async def on_mention_poll_create(
    client: WAHABot, chat_id: str, message_id: str, parsed, args, **kwargs
) -> Dict[str, Any]:
    is_group = parsed.get("is_group")

    messages = ["This is a polll"]
    poll_title = " ".join(args) or "Poll title"

    print("Creating new poll with args", args)

    if is_group:
        mentions = await get_mentions_list(
            client, chat_id, parsed.get("me", {}), admins_only=True
        )
        messages.append(" ".join(mentions))

    text_resp = await client.send(chat_id, "\n".join(messages))
    message_resp_id = text_resp.get("key", {}).get("id")
    message_resp_bool = text_resp.get("key", {}).get("fromMe", True)
    if message_resp_id:
        reply_to_id = f"{str(message_resp_bool).lower()}_{chat_id}_{message_resp_id}"
    else:
        reply_to_id = ""

    options = [
        f"Option {i+1}" for i in range(5)
    ]
    return await client.create_poll(chat_id, poll_title, options, True, reply_to_id)

async def on_mention_any(client: WAHABot, chat_id: str, message_id: str, parsed, args, **kwargs):
    ...

custom_commands_registry = {
    "on": [
        (on_mention_poll_create, "@poll")
    ],
    "on_mention": [
        (on_mention_any, None)
    ],
}
