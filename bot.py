import os
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

API_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}


def api_get(endpoint, params=None):
    try:
        response = requests.get(
            f"{API_URL}{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=20
        )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        return response.status_code, data

    except Exception as e:
        return 0, {"exception": str(e)}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mesaj = (
        "⚽ Futbol Botu Test Modunda!\n\n"
        "/test - API bağlantısını kontrol et\n"
        "/bugun - Bugünkü maçları getir\n"
        "/maclar - Önümüzdeki 7 günün maçları\n"
        "/superlig - Süper Lig maçları"
    )

    await update.message.reply_text(mesaj)


async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 API test ediliyor...")

    status_code, data = api_get("/status")

    if status_code != 200:
        await update.message.reply_text(
            f"❌ API HATASI\n\n"
            f"HTTP Kod: {status_code}\n"
            f"Detay:\n{data}"
        )
        return

    errors = data.get("errors", {})

    if errors:
        await update.message.reply_text(
            f"⚠️ API HATA VERDİ:\n\n{errors}"
        )
        return

    response = data.get("response", {})

    account = response.get("account", {})
    subscription = response.get("subscription", {})

    mesaj = (
        "✅ API BAĞLANTISI ÇALIŞIYOR\n\n"
        f"Plan: {subscription.get('plan', 'Bilinmiyor')}\n"
        f"İstek Bilgisi: {subscription.get('requests', 'Bilinmiyor')}\n\n"
        "Şimdi /bugun komutunu dene."
    )

    await update.message.reply_text(mesaj)


async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Bugünkü maçlar aranıyor...")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    status_code, data = api_get(
        "/fixtures",
        {
            "date": today
        }
    )

    if status_code != 200:
        await update.message.reply_text(
            f"❌ MAÇ VERİSİ ALINAMADI\n\n"
            f"HTTP Kod: {status_code}\n"
            f"API Detayı:\n{data}"
        )
        return

    errors = data.get("errors", {})

    if errors:
        await update.message.reply_text(
            f"⚠️ API HATASI:\n{errors}"
        )
        return

    matches = data.get("response", [])

    if not matches:
        await update.message.reply_text(
            f"ℹ️ {today} tarihinde API'de maç bulunamadı."
        )
        return

    mesajlar = []

    for match in matches[:30]:
        league = match["league"]["name"]
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        status = match["fixture"]["status"]["short"]

        mesajlar.append(
            f"🏆 {league}\n"
            f"⚽ {home} - {away}\n"
            f"📌 Durum: {status}"
        )

    full_text = "\n\n──────────────\n\n".join(mesajlar)

    for i in range(0, len(full_text), 4000):
        await update.message.reply_text(
            full_text[i:i + 4000]
        )


async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 Önümüzdeki 7 günün maçları aranıyor..."
    )

    today = datetime.now(timezone.utc)
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    status_code, data = api_get(
        "/fixtures",
        {
            "from": from_date,
            "to": to_date
        }
    )

    if status_code != 200:
        await update.message.reply_text(
            f"❌ MAÇ VERİSİ ALINAMADI\n\n"
            f"HTTP Kod: {status_code}\n"
            f"API Detayı:\n{data}"
        )
        return

    errors = data.get("errors", {})

    if errors:
        await update.message.reply_text(
            f"⚠️ API HATASI:\n{errors}"
        )
        return

    matches = data.get("response", [])

    if not matches:
        await update.message.reply_text(
            f"ℹ️ {from_date} - {to_date} arasında maç bulunamadı."
        )
        return

    mesajlar = []

    for match in matches[:50]:
        league = match["league"]["name"]
        country = match["league"]["country"]

        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]

        date = match["fixture"]["date"][:16].replace("T", " ")

        mesajlar.append(
            f"🏆 {league} ({country})\n"
            f"📅 {date} UTC\n"
            f"⚽ {home} - {away}"
        )

    full_text = "\n\n──────────────\n\n".join(mesajlar)

    for i in range(0, len(full_text), 4000):
        await update.message.reply_text(
            full_text[i:i + 4000]
        )


async def superlig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇹🇷 Süper Lig maçları aranıyor..."
    )

    today = datetime.now(timezone.utc)
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")

    status_code, data = api_get(
        "/fixtures",
        {
            "league": 203,
            "season": 2026,
            "from": from_date,
            "to": to_date
        }
    )

    if status_code != 200:
        await update.message.reply_text(
            f"❌ SÜPER LİG VERİSİ ALINAMADI\n\n"
            f"HTTP Kod: {status_code}\n"
            f"API Detayı:\n{data}"
        )
        return

    errors = data.get("errors", {})

    if errors:
        await update.message.reply_text(
            f"⚠️ API HATASI:\n{errors}"
        )
        return

    matches = data.get("response", [])

    if not matches:
        await update.message.reply_text(
            "ℹ️ Önümüzdeki 14 gün için Süper Lig maçı bulunamadı."
        )
        return

    mesajlar = []

    for match in matches:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]

        date = match["fixture"]["date"][:16].replace("T", " ")

        mesajlar.append(
            f"🇹🇷 SÜPER LİG\n"
            f"📅 {date} UTC\n"
            f"⚽ {home} - {away}"
        )

    full_text = "\n\n──────────────\n\n".join(mesajlar)

    for i in range(0, len(full_text), 4000):
        await update.message.reply_text(
            full_text[i:i + 4000]
        )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_api))
    app.add_handler(CommandHandler("bugun", bugun))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("superlig", superlig))

    print("Futbol Botu başlatıldı...")

    app.run_polling()


if __name__ == "__main__":
    main()
