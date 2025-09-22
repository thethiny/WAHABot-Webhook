import asyncio
import random
from typing import Any, Awaitable, Callable, Dict, List, Optional, overload

from fastapi import FastAPI, Request
import httpx

from src.utils import parse_mentions_for_sending

class WAHABot:
    IGNORE_MESSAGES_SET = set()

    MESSAGES_HISTORY = {
        # chat_id: last_message_id
    }

    def __init__(self, base_url, api_key, session, timeout: float = 10,
        wpm: float = 125, t_min: float = 0.9,t_max: float = 8, jitter: float = 0.2,
        webhook_func: Callable = lambda *args: print(f"Webhook stub"),
        notifs_admins: List[str] = [],
    ):
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key
        self.session = session
        self.timeout = timeout
        self.wpm = wpm
        self.t_min = t_min
        self.t_max = t_max
        self.jitter = jitter
        self._handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._mentions_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._mention_no_cmd_handlers: List[Callable[..., Awaitable[Any]]] = []
        self._no_cmd_handlers: List[Callable[..., Awaitable[Any]]] = []
        self._status_handlers: List[Callable[..., Awaitable[Any]]] = []
        self.admins = notifs_admins

        self.http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
        )

        def make_webhook_handler(webhook_func):
            async def handler(request: Request):
                return await webhook_func(self, request)
            return handler

        self.app = FastAPI()
        self.app.add_api_route("/", make_webhook_handler(webhook_func), methods=["POST"])

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = await self.http.post(path, json=payload)
        r.raise_for_status()
        return r.json() if r.content else {}

    async def _get(self, path: str) -> Any:
        r = await self.http.get(path)
        r.raise_for_status()
        return r.json() if r.content else {}

    async def mark_seen(self, chat_id: str, message_id: str):
        if not message_id or not chat_id:
            raise ValueError(f"Must provide message_id and chat_id")
        body = {
            "chatId": chat_id,
            "messageIds": [message_id],
            "participant": None,
            "session": self.session
        }

        try:
            results = await self._post("/api/sendSeen", body)
            self.MESSAGES_HISTORY.pop(chat_id, None)
            return results
        except Exception as e:
            print(f"Error marking {message_id} in char {chat_id} as seen: {e}")
            return None

    async def presence(self, chat_id: Optional[str], status: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {"presence": status}
        if chat_id:
            body["chatId"] = chat_id
        return await self._post(f"/api/{self.session}/presence", body)  # typing/paused/offline.

    async def start_typing(self, chat_id: str):
        return await self.presence(chat_id, "typing")

    async def stop_typing(self, chat_id: str):
        return await self.presence(chat_id, "paused")

    async def get_group_members(self, chat_id: str) -> List[Dict[str, Optional[str]]]:
        if not chat_id:
            raise ValueError(f"Missing group chat id!")
        return await self._get(f"/api/{self.session}/groups/{chat_id}/participants")

    async def _create_poll(self, chat_id: str, name: str, options: List[str], multi: bool = False, reply_to: str = "") -> Dict[str, Any]:
        body = {
            "chatId": chat_id,
            "session": self.session,
            "poll": {
                "name": name,
                "options": options[:12],
                "multipleAnswers": multi,
            }
        }

        if reply_to:
            body["reply_to"] = reply_to

        return await self._post("/api/sendPoll", body)

    async def create_poll(self, chat_id: str, name: str, options: List[str], multi: bool = False, reply_to: str = "") -> Dict[str, Any]:
        mark_seen_error = await self.mark_chat_as_seen(chat_id, reply_to)
        return await self._create_poll(chat_id, name, options, multi, reply_to)

    async def _send_text(self, chat_id: str, text: str, reply_to: Optional[str] = None, mentions: List[str] = []):
        body = {
            "session": self.session,
            "chatId": chat_id,
            "text": text
        }
        if reply_to:
            body["reply_to"] = reply_to

        if mentions:
            body["mentions"] = mentions

        return await self._post("/api/sendText", body)

    async def mark_chat_as_seen(self, chat_id, reply_to):
        try:
            if reply_to:
                print("Marking Seen for reply")
                await self.mark_seen(chat_id, reply_to)
            elif chat_id in self.MESSAGES_HISTORY:
                print("Marking Seen for normal chat")
                to_mark = self.MESSAGES_HISTORY[chat_id]
                await self.mark_seen(chat_id, to_mark)
            else:
                print(f"No message to mark as seen in {chat_id}")
        except Exception as e:
            print(f"Error marking as seen in {chat_id}: {e}")
            return e

    async def prepare_to_send_text(self, chat_id: str, text: str, reply_to: Optional[str] = None, mentions = []):
        mark_seen_error = await self.mark_chat_as_seen(chat_id, reply_to)

        try:
            await self.initiate_typing_process(chat_id, text, mentions)
        except Exception as e:
            print(f"Error handling `typing...` in {chat_id}: {e}")
            # Allow to send without typing

    async def initiate_typing_process(self, chat_id, text, mentions = []):
        try:
            await self.start_typing(chat_id)
            await asyncio.sleep(min(self._estimate_typing_seconds(text, mentions), 60))
        except Exception as e:
            print(f"Error typing in {chat_id}")
            raise e

        try:
            await self.stop_typing(chat_id)
        except Exception as e:
            print(f"Error pausing in {chat_id}")

    def _estimate_typing_seconds(self, text: str, mentions=[]) -> float:
        cps = (self.wpm * 5.0) / 60.0
        base_len = len(text)

        # Reduce cost of mentions
        mention_chars = sum(len(m) for m in mentions)
        adjusted_len = base_len - (mention_chars * 0.75)  # 80% discount

        base = adjusted_len / max(cps, 1e-6)
        base = max(self.t_min, min(self.t_max, base))
        jitter = base * self.jitter
        return max(self.t_min, min(self.t_max, base + random.uniform(-jitter, jitter)))

    async def send(self, chat_id: str, text: str, reply_to: Optional[str] = None):
        text, mentions = parse_mentions_for_sending(text)
        await self.prepare_to_send_text(chat_id, text, reply_to, mentions)
        return await self._send_text(chat_id, text, reply_to, mentions)

    # Decorators
    def on(self, command: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        key = command.strip().lower()

        def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self._handlers[key] = fn
            return fn

        return deco
    
    @overload
    def on_mention(self, mentioned: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]: ...
    @overload
    def on_mention(self, mentioned: None = None) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]: ...

    def on_mention(
        self, mentioned: Optional[str] = None
    ) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            if mentioned is None:
                self._mention_no_cmd_handlers.append(fn)
            else:
                self._mentions_handlers[mentioned] = fn
            return fn

        return deco
    
    def on_text(self) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
        def deco(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
            self._no_cmd_handlers.append(fn)
            return fn

        return deco
