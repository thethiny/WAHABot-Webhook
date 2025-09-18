from src.custom_client import WAHABot


async def get_mentions_list(client: WAHABot, chat_id, me={}, admins_only=True):
    my_id = me.get("id", "")
    my_jid = me.get("jid", "")
    my_label = me.get("label", "")

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
