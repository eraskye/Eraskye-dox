# CLOVISS SYSTEM PYDXSN

Cyber-security dashboard that wraps the `soft.py` Jitler API client behind a
Flask backend with a license system, admin panel and Telegram bot.

## 1. Run on Replit

1. Upload/import this project.
2. Add the Replit Secrets (see §2).
3. Press **Run**. Replit executes:
   ```
   python backend/app.py
   ```
   Default port is `3000`.

## 2. Replit Secrets (all required)

| Secret | Purpose |
|---|---|
| `JITLER_API_KEY` | Bearer token for `https://api.jitler.top` (from `soft.py`). **Never in the frontend.** |
| `SECRET_KEY` | Flask session signing key — any long random string. |
| `ADMIN_USERNAME` | Admin panel login. |
| `ADMIN_PASSWORD` | Admin panel password. |
| `TELEGRAM_BOT_TOKEN` | From @BotFather. |
| `ADMIN_TELEGRAM_ID` | Your numeric Telegram user ID. |

Optional: `JITLER_BASE_URL`, `JITLER_POLL_TIMEOUT`, `PORT`, `DB_PATH`.

## 3. Start the Telegram bot

In a second Replit Shell:

```bash
python backend/telegram_bot.py
```

Admin-only commands:

```
/start
/help
/gen 1
/gen 3
/gen 7
/gen 30
```

## 4. Create licenses

- **Telegram**: `/gen 7` → returns a new 7-day key.
- **Admin panel**: open `/admin`, sign in, choose a duration, click Generate.

## 5. One-device system

1. User opens the dashboard, enters a key, clicks **Activate**.
2. The browser generates a random `device_id` (stored in `localStorage`) and sends it to `/api/license/check`.
3. On the first successful activation, the server permanently binds the key to that `device_id` and sets `expires_at = now + duration`.
4. Any other `device_id` gets `DEVICE_MISMATCH`.
5. Expiry is enforced **server-side** on every request — the browser clock is ignored.

## 6. What actually talks to Jitler

`backend/api_client.py` mirrors `soft.py` exactly:

```
POST /search   {type, query, page}   Authorization: Bearer <key>
GET  /search/{id}                    Authorization: Bearer <key>   (polling, 501 = pending)
GET  /me                             Authorization: Bearer <key>
```

The polling timeout is 60 s (same as `soft.py`).
