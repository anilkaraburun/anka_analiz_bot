import os
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Tokenlar
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}

# Ortak API İstek Fonksiyonu
def api_get(endpoint, params=None):
    url = f"{API_URL}{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"errors": str(e)}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ Futbol Botu test modunda başlatıldı!\n\n"
        "Komutlar:\n"
        "/test - API bağlantısını sınar\n"
        "/bugun - Bugünkü maçları listeler\n"
        "/maclar - 3 Büyük ligin 7 günlük maçlarını getirir\n"
        "/superlig - Süper Lig'in 14 günlük maçlarını getirir"
    )

async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("API bağlantısı test ediliyor...")
    
    status_code, data = api_get("/status")
    
    if status_code != 200:
        await update.message.reply_text(f"❌ HTTP HATA: {status_code}\nDetay: {data}")
        return
        
    errors = data.get("errors", {})
    if errors:
        await update.message.reply_text(f"⚠️ API HATASI:\n{errors}")
        return
        
    account = data.get("response", {}).get("account", {})
    reqs = data.get("response", {}).get("subscription", {}).get("requests", {})
    
    await update.message.reply_text(
        f"✅ API BAĞLANTISI KUSURSUZ!\n"
        f"Kullanıcı: {account.get('firstname')}\n"
        f"İstek Durumu: {reqs.get('current')} / {reqs.get('limit_day')}"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bugünkü maçlar aranıyor...")
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    status_code, data = api_get("/fixtures", {"date": today})
    
    if status_code != 200:
        await update.message.reply_text(f"❌ BAĞLANTI HATASI\nHTTP Kod: {status_code}\nDetay:\n{data}")
        return
        
    errors = data.get("errors", {})
    if errors:
        await update.message.reply_text(f"⚠️ API HATASI:\n{errors}")
        return
        
    matches = data.get("response", [])
    if not matches:
        await update.message.reply_text("ℹ️ Bugün için herhangi bir maç bulunamadı.")
        return
        
    mesajlar = [f"📅 {today} Maçları: Toplam {len(matches)} maç bulundu. (Sadece ilk 15'i gösteriliyor)"]
    
    for match in matches[:15]:
        home = match["teams"]["home"]["name"]
        away = match["teams"]["away"]["name"]
        league = match["league"]["name"]
        mesajlar.append(f"🏆 {league}\n⚽ {home} - {away}")
        
    await update.message.reply_text("\n\n──────────────\n\n".join(mesajlar))

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Seçili ligler için önümüzdeki 7 günün maçları aranıyor...")
    
    today = datetime.now(timezone.utc)
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    leagues = {
        203: "🇹🇷 Süper Lig",
        39: "🏴 Premier League",
        140: "🇪🇸 La Liga"
    }

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

        if status_code != 200:
            mesajlar.append(f"❌ {league_name}\nHTTP: {status_code}\n{data}")
            continue

        errors = data.get("errors", {})
        if errors:
            mesajlar.append(f"⚠️ {league_name}\nAPI Hatası: {errors}")
            continue

        matches = data.get("response", [])
        if not matches:
            mesajlar.append(f"ℹ️ {league_name} için bu tarihlerde maç yok.")
            continue

        for match in matches:
            home = match["teams"]["home"]["name"]
            away = match["teams"]["away"]["name"]
            date = match["fixture"]["date"][:16].replace("T", " ")

            mesajlar.append(
                f"{league_name}\n"
                f"📅 {date} UTC\n"
                f"⚽ {home} - {away}"
            )

    if not mesajlar:
        await update.message.reply_text("ℹ️ Önümüzdeki 7 gün içinde seçili liglerde maç bulunamadı.")
        return

    full_text = "\n\n──────────────\n\n".join(mesajlar)
    for i in range(0, len(full_text), 4000):
        await update.message.reply_text(full_text[i:i + 4000])

async def superlig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🇹🇷 Süper Lig maçları aranıyor...")

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
        await update.message.reply_text(f"❌ SÜPER LİG VERİSİ ALINAMADI\n\nHTTP Kod: {status_code}\nAPI Detayı:\n{data}")
        return

    errors = data.get("errors", {})
    if errors:
        await update.message.reply_text(f"⚠️ API HATASI:\n{errors}")
        return

    matches = data.get("response", [])
    if not matches:
        await update.message.reply_text("ℹ️ Önümüzdeki 14 gün için Süper Lig maçı bulunamadı.")
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
        await update.message.reply_text(full_text[i:i + 4000])

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_api))
    app.add_handler(CommandHandler("bugun", bugun))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("superlig", superlig))

    print("⚽ Futbol Botu başarıyla başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
