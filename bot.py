import os
import requests

from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)


# =========================
# AYARLAR
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

API_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}


# =========================
# API İSTEK FONKSİYONU
# =========================

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
            data = {
                "raw": response.text
            }

        return response.status_code, data

    except Exception as e:

        return 0, {
            "exception": str(e)
        }


# =========================
# START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    mesaj = (
        "⚽ FUTBOL ANALİZ BOTU\n\n"

        "Komutlar:\n\n"

        "/test - API bağlantısını test et\n"
        "/bugun - Bugünkü maçları getir\n"
        "/maclar - Önümüzdeki 7 gün\n"
        "/superlig - Süper Lig maçları"
    )

    await update.message.reply_text(mesaj)


# =========================
# API TEST
# =========================

async def test_api(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🔍 API bağlantısı test ediliyor..."
    )

    status_code, data = api_get("/status")

    if status_code != 200:

        await update.message.reply_text(
            f"❌ API BAĞLANTI HATASI\n\n"
            f"HTTP Kod: {status_code}\n\n"
            f"Detay:\n{data}"
        )

        return

    errors = data.get("errors", {})

    if errors:

        await update.message.reply_text(
            f"⚠️ API HATASI:\n\n{errors}"
        )

        return

    response = data.get("response", {})

    subscription = response.get(
        "subscription",
        {}
    )

    account = response.get(
        "account",
        {}
    )

    mesaj = (
        "✅ API BAĞLANTISI ÇALIŞIYOR\n\n"

        f"Plan: "
        f"{subscription.get('plan', 'Bilinmiyor')}\n\n"

        f"Hesap: "
        f"{account.get('email', 'Bilinmiyor')}\n\n"

        "Şimdi /maclar komutunu deneyebilirsin."
    )

    await update.message.reply_text(mesaj)


# =========================
# BUGÜNKÜ MAÇLAR
# =========================

async def bugun(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "⚽ Bugünkü maçlar aranıyor..."
    )

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    status_code, data = api_get(

        "/fixtures",

        {
            "date": today
        }

    )

    if status_code != 200:

        await update.message.reply_text(

            f"❌ MAÇ VERİSİ ALINAMADI\n\n"
            f"HTTP Kod: {status_code}\n\n"
            f"Detay:\n{data}"

        )

        return

    errors = data.get("errors", {})

    if errors:

        await update.message.reply_text(
            f"⚠️ API HATASI:\n\n{errors}"
        )

        return

    matches = data.get(
        "response",
        []
    )

    if not matches:

        await update.message.reply_text(
            f"ℹ️ {today} tarihinde maç bulunamadı."
        )

        return

    mesajlar = []

    for match in matches[:40]:

        league = match["league"]["name"]

        home = match["teams"]["home"]["name"]

        away = match["teams"]["away"]["name"]

        status = match["fixture"]["status"]["short"]

        date = match["fixture"]["date"][:16]

        mesaj = (

            f"🏆 {league}\n"

            f"📅 {date}\n"

            f"⚽ {home} - {away}\n"

            f"📌 Durum: {status}"

        )

        mesajlar.append(mesaj)

    full_text = "\n\n──────────────\n\n".join(
        mesajlar
    )

    for i in range(
        0,
        len(full_text),
        4000
    ):

        await update.message.reply_text(

            full_text[i:i + 4000]

        )


# =========================
# ÖNÜMÜZDEKİ MAÇLAR
# =========================

async def maclar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📅 Önümüzdeki 7 günün maçları aranıyor..."
    )

    today = datetime.now(
        timezone.utc
    )

    from_date = today.strftime(
        "%Y-%m-%d"
    )

    to_date = (
        today + timedelta(days=7)
    ).strftime(
        "%Y-%m-%d"
    )


    # LİGLER

    leagues = {

        203: "🇹🇷 Süper Lig",

        39: "🏴 Premier League",

        140: "🇪🇸 La Liga"

    }


    # 2026-2027 SEZONU

    season = 2026


    mesajlar = []


    for league_id, league_name in leagues.items():

        status_code, data = api_get(

            "/fixtures",

            {

                "league": league_id,

                "season": season,

                "from": from_date,

                "to": to_date

            }

        )


        # HTTP HATASI

        if status_code != 200:

            mesajlar.append(

                f"❌ {league_name}\n\n"

                f"HTTP Hatası: {status_code}\n"

                f"Detay:\n{data}"

            )

            continue


        # API HATASI

        errors = data.get(
            "errors",
            {}
        )

        if errors:

            mesajlar.append(

                f"⚠️ {league_name}\n\n"

                f"API Hatası:\n{errors}"

            )

            continue


        matches = data.get(
            "response",
            []
        )


        # MAÇ YOKSA

        if not matches:

            continue


        # MAÇLARI LİSTELE

        for match in matches:

            home = match["teams"]["home"]["name"]

            away = match["teams"]["away"]["name"]

            date = match["fixture"]["date"][:16]

            status = match["fixture"]["status"]["short"]


            mesaj = (

                f"{league_name}\n\n"

                f"📅 {date}\n"

                f"⚽ {home} - {away}\n"

                f"📌 Durum: {status}"

            )

            mesajlar.append(mesaj)


    # HİÇ MAÇ YOKSA

    if not mesajlar:

        await update.message.reply_text(

            "ℹ️ Önümüzdeki 7 gün içinde "
            "seçili liglerde maç bulunamadı."

        )

        return


    full_text = "\n\n──────────────\n\n".join(
        mesajlar
    )


    # TELEGRAM MESAJ SINIRI

    for i in range(

        0,

        len(full_text),

        4000

    ):

        await update.message.reply_text(

            full_text[i:i + 4000]

        )


# =========================
# SÜPER LİG
# =========================

async def superlig(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🇹🇷 Süper Lig maçları aranıyor..."
    )

    today = datetime.now(
        timezone.utc
    )

    from_date = today.strftime(
        "%Y-%m-%d"
    )

    to_date = (

        today + timedelta(days=14)

    ).strftime(
        "%Y-%m-%d"
    )


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

            f"HTTP Kod: {status_code}\n\n"

            f"Detay:\n{data}"

        )

        return


    errors = data.get(
        "errors",
        {}
    )


    if errors:

        await update.message.reply_text(

            f"⚠️ API HATASI:\n\n{errors}"

        )

        return


    matches = data.get(
        "response",
        []
    )


    if not matches:

        await update.message.reply_text(

            "ℹ️ Önümüzdeki 14 gün için "
            "Süper Lig maçı bulunamadı."

        )

        return


    mesajlar = []


    for match in matches:

        home = match["teams"]["home"]["name"]

        away = match["teams"]["away"]["name"]

        date = match["fixture"]["date"][:16]

        status = match["fixture"]["status"]["short"]


        mesaj = (

            "🇹🇷 SÜPER LİG\n\n"

            f"📅 {date}\n"

            f"⚽ {home} - {away}\n"

            f"📌 Durum: {status}"

        )


        mesajlar.append(mesaj)


    full_text = "\n\n──────────────\n\n".join(
        mesajlar
    )


    for i in range(

        0,

        len(full_text),

        4000

    ):

        await update.message.reply_text(

            full_text[i:i + 4000]

        )


# =========================
# BOTU BAŞLAT
# =========================

def main():

    if not TELEGRAM_TOKEN:

        print(
            "HATA: TELEGRAM_TOKEN bulunamadı!"
        )

        return


    if not FOOTBALL_TOKEN:

        print(
            "HATA: FOOTBALL_TOKEN bulunamadı!"
        )

        return


    app = Application.builder().token(
        TELEGRAM_TOKEN
    ).build()


    app.add_handler(

        CommandHandler(
            "start",
            start
        )

    )


    app.add_handler(

        CommandHandler(
            "test",
            test_api
        )

    )


    app.add_handler(

        CommandHandler(
            "bugun",
            bugun
        )

    )


    app.add_handler(

        CommandHandler(
            "maclar",
            maclar
        )

    )


    app.add_handler(

        CommandHandler(
            "superlig",
            superlig
        )

    )


    print(
        "⚽ Futbol Botu başarıyla başlatıldı..."
    )


    app.run_polling()


# =========================
# ÇALIŞTIR
# =========================

if __name__ == "__main__":

    main()
