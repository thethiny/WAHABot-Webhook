# WhatsApp Bot for WAHA

This project provides a FastAPI-based webhook that extends [WAHA](https://waha.devlike.pro/) (WhatsApp HTTP API) with custom automations. Docker Compose runs two services: the upstream WAHA container and this Python webhook.

## Prerequisites
- Docker Engine and Docker Compose plugin
- Access to the [`devlikeapro/waha`](https://hub.docker.com/r/devlikeapro/waha) Docker image
- (Optional) Python 3.9+ if you prefer to run the webhook locally without Docker

## Repository Layout
- [`docker-compose.yaml`](docker-compose.yaml) - orchestrates WAHA and the webhook service
- [`Dockerfile`](Dockerfile) - builds the webhook image that runs `python -m main`
- [`src/`](src/) - FastAPI webhook, WAHA client wrapper, and helper utilities
- [`commands/`](commands/) - drop-in folder for custom bot commands (see [`commands/custom_command_example.py`](commands/custom_command_example.py))

## Quick Start
1. Create the WAHA configuration at the repo root as `.env` (used by the `waha` service in `docker-compose.yaml`). Start from the minimal template in the next section and adjust values for your deployment.
2. Create `webhook.env` alongside the compose file for the webhook container. A minimal template is provided below.
3. (Optional) Tune the forwarded ports by setting `WAHA_PORT` and `WEBHOOK_PORT` in your shell or in `.env` before you run Compose. Defaults are 13000 and 13001.
4. Launch both services:
   ```bash
   docker compose up -d
   ```
5. Verify the services:
   - Webhook: `curl http://localhost:${WEBHOOK_PORT:-13001}/healthcheck`
   - WAHA dashboard (if enabled): `http://localhost:${WAHA_PORT:-13000}`

The helper script [`build_and_run_webhook.sh`](build_and_run_webhook.sh) still relies on `.env` when you build/run the webhook locally without Compose.

## Runtime Endpoints
- `POST /` - WAHA sends incoming WhatsApp events to this endpoint
- `POST /send` - send a message through WAHA (requires `X-Api-Key` header matching `BOT_API_KEY`)
- `GET /healthcheck` - lightweight status probe used by the Docker healthcheck

## Environment Variables
The snippets below focus on the minimum needed to recreate this repository. Review the [WAHA configuration guide](https://waha.devlike.pro/docs/how-to/config/) for additional flags.

### WAHA service (`.env` for the `waha` container)
```env
WAHA_API_KEY=sha512:REPLACE_WITH_SHA512_HASH
WHATSAPP_API_SCHEMA=http
WHATSAPP_API_HOSTNAME=0.0.0.0
WHATSAPP_API_PORT=13000
WHATSAPP_DEFAULT_ENGINE=NOWEB
WHATSAPP_START_SESSION=default
WAHA_AUTO_START_DELAY_SECONDS=1
WHATSAPP_HOOK_URL=http://waha_webhook:${WEBHOOK_PORT:-13001}/
WHATSAPP_HOOK_EVENTS=session.status,message
WAHA_MEDIA_STORAGE=LOCAL
WHATSAPP_FILES_FOLDER=/app/.media
WHATSAPP_DOWNLOAD_MEDIA=false
WAHA_LOG_LEVEL=info
WAHA_PRINT_QR=false
TZ=UTC
```

Common optional toggles (add only the ones you need):
```env
# Session filtering
WAHA_SESSION_CONFIG_IGNORE_STATUS=true
WAHA_SESSION_CONFIG_IGNORE_CHANNELS=true
WAHA_SESSION_CONFIG_IGNORE_BROADCAST=true

# Dashboard / Swagger access
WAHA_DASHBOARD_ENABLED=true
WAHA_DASHBOARD_USERNAME=admin
WAHA_DASHBOARD_PASSWORD=CHANGE_ME
WHATSAPP_SWAGGER_ENABLED=true
WHATSAPP_SWAGGER_USERNAME=swagger
WHATSAPP_SWAGGER_PASSWORD=CHANGE_ME_TOO

# Webhook retry policy
WHATSAPP_HOOK_RETRIES_ATTEMPTS=3
WHATSAPP_HOOK_RETRIES_DELAY_SECONDS=5

# Media handling
WHATSAPP_DOWNLOAD_MEDIA=true
WHATSAPP_FILES_MIMETYPES=image/jpeg,image/png
```

### Webhook service (`webhook.env` for the `waha_webhook` container)
```env
BOT_URL=http://waha:${WAHA_PORT:-13000}
BOT_API_KEY=REPLACE_WITH_PLAIN_TOKEN
WEBHOOK_PORT=13001
NOTIFS_ADMINS=15551234567@c.us,1522123559876543@g.us

# Optional integrations
LLM_API=cerebras
CEREBRAS_API_KEY=REPLACE_WITH_CEREBRAS_TOKEN
CEREBRAS_API_MODEL=llama-3.3-70b
```
`BOT_API_KEY` must match the plain token that you hash into `WAHA_API_KEY`. WAHA expects `sha512:HEX_DIGEST`, while the webhook checks the un-hashed token provided in the `X-Api-Key` header.

## Custom Commands
- Implement new handlers in [`commands/custom_commands.py`](commands/custom_commands.py) (git-ignored by default).
- Register handlers in `custom_commands_registry` as demonstrated in [`commands/custom_command_example.py`](commands/custom_command_example.py) - supports `@bot.on`, `@bot.on_mention`, and media-specific hooks.

## Read More
- WAHA quick start and configuration: https://waha.devlike.pro/docs/how-to/config/
- Full WAHA documentation index: https://waha.devlike.pro/
- Docker image (pinned latest digest): https://hub.docker.com/layers/devlikeapro/waha/latest/images/sha256-77ac87952caa42e10b16b2dc7161bcd296f006a47b7bf958017f87d81c89b7eb

These links cover the upstream WAHA project. This README documents only the pieces needed to recreate this repository on top of WAHA.