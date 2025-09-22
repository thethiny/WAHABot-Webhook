from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.custom_client import WAHABot  # only for type checking

import re

WA_DOMAINS = ["c.us", "lid", "s.whatsapp.net"]
DOMAINS_RE = "|".join(re.escape(d) for d in WA_DOMAINS)
MENTIONS_RE = re.compile(rf"@(\d+)@({DOMAINS_RE})")
MENTIONS_RECV_RE = re.compile(r"@(\d+)")

async def get_mentions_list(client: "WAHABot", chat_id, me={}, admins_only=True):
    my_id = me.get("id", "")
    my_jid = me.get("jid", "")
    my_label = me.get("lid", "")

    messages = []
    group_members = await client.get_group_members(chat_id)
    for member in group_members:
        target_id = member.get("lid") or member.get("id") or member.get("jid") # id is either jid or lid or c.us id. jid is <phone>@s.whatsapp.net. lid is <label>@lid. c.us is <phone>@c.us
        admin_type = member.get("admin", None)
        if not target_id:
            continue

        if admins_only and not admin_type:
            continue

        if me and (target_id == my_id or target_id == my_label or target_id == my_jid):
            print("Not mentioning self!")
            continue

        # TODO: Support removing the requestor by passing # Edit: Not possible cuz sender is c.us but group people are s.whatsapp.net

        messages.append("@" + target_id)
    return messages

def parse_mentions_for_sending(text):
    matches = MENTIONS_RE.findall(text)
    mentions = list(set([f"{m[0]}@{m[1]}" for m in matches]))

    text = MENTIONS_RE.sub(r"@\1", text)

    return text, mentions

def get_mentions(text):
    matches = MENTIONS_RECV_RE.findall(text)
    mentions = list(set(matches))
    return mentions

def is_mention(text):
    return bool(MENTIONS_RE.match(text))

def has_mentions(text):
    return bool(parse_mentions_for_sending(text)[1])

def is_mentioned(text, user):
    suffixes = ("@c.us", "@lid", "@s.whatsapp.net")
    mentions = {m + s for m in get_mentions(text) for s in suffixes}
    return any(
        u and u in mentions for u in (user.get("id"), user.get("jid"), user.get("lid"))
    )
