import os
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Tokenlar (Railway'de environment variable olarak gireceğiz)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

headers = {"X-Auth-Token": FOOTBALL_TOKEN}

ISTENEN_LIGLER = [
    "Premier League", "Primera Division", "Serie A",
    "Bundesliga", "Ligue 1", "UEFA Champions League", "Champions League"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba!\n\n"
        "Komutlar:\n"
        "/maclar - Önümüzdeki 10 günün yüksek güvenli maçları\n"
        "/canli - Şu anki canlı maçlar"
    )

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Maçlar analiz ediliyor, biraz bekle...")

    today = datetime.utcnow().date()
    end_date = today + timedelta(days=10)

    url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        await update.message.reply_text("Veri alınamadı. Token'ları kontrol et.")
        return

    matches = response.json().get("matches", [])
    filtered = [m for m in matches if any(l.lower() in m["competition"]["name"].lower() for l in ISTENEN_LIGLER)]

    if not filtered:
        await update.message.reply_text("Önümüzdeki 10 günde uygun maç bulunamadı.")
        return

    # Puan durumları
    competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
    standings_cache = {}

    for comp_id in competitions:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers)
        if r.status_code == 200:
            tables = r.json().get("standings", [])
            if tables:
                table = tables[0].get("table", [])
                team_pos = {
                    row["team"]["id"]: {
                        "position": row["position"],
                        "played": row["playedGames"],
                        "goals_for": row.get("goalsFor", 0)
                    } for row in table
                }
                if team_pos:
                    standings_cache[comp_id] = team_pos

    filtered.sort(key=lambda x: x["utcDate"])
    mesajlar = []

    for match in filtered:
        status = match["status"]
        if status == "FINISHED":
            continue

        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]
        competition = match["competition"]["name"]
        utc_date = match["utcDate"][:16].replace("T", " ")
        home_id = match["homeTeam"]["id"]
        away_id = match["awayTeam"]["id"]
        comp_id = match["competition"]["id"]

        score = match.get("score", {}).get("fullTime", {})
        home_score = score.get("home")
        away_score = score.get("away")

        is_live = status in ["LIVE", "IN_PLAY", "PAUSED"]

        if is_live:
            sinyal = f"🔴 CANLI ({home_score}-{away_score})"
            guven = "Canlı"
            if home_score == away_score:
                yorum = "Beraberlik var."
            elif home_score > away_score:
                yorum = "Ev sahibi önde. 1X güçleniyor."
            else:
                yorum = "Deplasman önde. X2 güçleniyor."
            
            text = (
                f"🏆 {competition}\n"
                f"📅 {utc_date} UTC\n"
                f"🏠 {home}\n"
                f"🚪 {away}\n"
                f"🎯 {sinyal}\n"
                f"💬 {yorum}\n"
            )
            mesajlar.append(text)
            continue

        # Planlanmış maç
        team_pos = standings_cache.get(comp_id, {})
        home_info = team_pos.get(home_id)
        away_info = team_pos.get(away_id)

        if not (home_info and away_info and home_info["played"] >= 2 and away_info["played"] >= 2):
            continue

        pos_diff = away_info["position"] - home_info["position"]

        if pos_diff >= 7:
            sinyal = "1️⃣ (Güçlü Favori)"
            guven = "Yüksek"
        elif pos_diff >= 4:
            sinyal = "1️⃣ veya 1X"
            guven = "Orta-Yüksek"
        else:
            continue  # Sadece Yüksek ve Orta-Yüksek

        text = (
            f"🏆 {competition}\n"
            f"📅 {utc_date} UTC\n"
            f"🏠 {home}\n"
            f"🚪 {away}\n"
            f"🎯 {sinyal} (Güven: {guven})\n"
        )
        mesajlar.append(text)

    if not mesajlar:
        await update.message.reply_text("Şu anda Yüksek / Orta-Yüksek güvenli maç bulunmuyor.")
    else:
        # Telegram mesaj limiti nedeniyle parçala
        full_text = "\n────────────────────\n".join(mesajlar)
        if len(full_text) > 4000:
            for i in range(0, len(full_text), 4000):
                await update.message.reply_text(full_text[i:i+4000])
        else:
            await update.message.reply_text(full_text)

async def canli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maclar(update, context)  # Şimdilik aynı fonksiyonu kullanıyoruz

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("canli", canli))
    print("Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()