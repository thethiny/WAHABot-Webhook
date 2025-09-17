from src.custom_client import WAHABot


async def get_mentions_list(client: WAHABot, chat_id, me={}, admins_only=True):
    my_id = me.get("id", "")
    my_label = me.get("label", "")

    messages = []
    group_members = await client.get_group_members(chat_id)
    for member in group_members:
        target_id = member.get("id", member.get("lid", ""))
        admin_type = member.get("admin", None)
        if not target_id:
            continue

        if admins_only and not admin_type:
            continue

        if me and target_id == my_id or target_id == my_label:
            print("Not mentioning self!")
            continue

        messages.append("@" + target_id)
    return messages
