import os
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Tokenlar
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
headers = {"X-Auth-Token": FOOTBALL_TOKEN}

ISTENEN_LIGLER = [
    "Premier League", "Primera Division", "Serie A",
    "Bundesliga", "Ligue 1", "UEFA Champions League", "Champions League",
    "Super Lig", "Süper Lig"
]

def parse_form(form_str):
    """Son 5 maçlık form verisini (W,D,L) puan ortalamasına (0-3 arası) çevirir."""
    if not form_str:
        return 1.0  # Veri yoksa nötr (1 puan) varsay
    form_str = form_str.replace(",", "").replace(" ", "").upper()
    if not form_str:
        return 1.0
    pts = sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str)
    return pts / len(form_str)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! Gelişmiş Algoritma devrede. 🤖\n\n"
        "Komutlar:\n"
        "/maclar - İstatistiksel yapay zeka analizli maçlar\n"
        "/canli - Şu anki canlı maçlar"
    )

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Maçlar form, iç/dış saha ve averaj çaprazlamasıyla analiz ediliyor, lütfen bekle...")
    
    today = datetime.utcnow().date()
    end_date = today + timedelta(days=10)
    
    url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        await update.message.reply_text("Veri alınamadı. API Token limitini doldurmuş olabilirsin.")
        return
        
    matches = response.json().get("matches", [])
    filtered = [m for m in matches if any(l.lower() in m["competition"]["name"].lower() for l in ISTENEN_LIGLER)]
    
    if not filtered:
        await update.message.reply_text("Önümüzdeki 10 günde belirtilen liglerde maç bulunamadı.")
        return

    # Liglerin puan durumlarını çek (TOTAL, HOME, AWAY ayrı ayrı)
    competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
    standings_cache = {}
    
    for comp_id in competitions:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers)
        if r.status_code == 200:
            tables = r.json().get("standings", [])
            total_table = next((t["table"] for t in tables if t["type"] == "TOTAL"), [])
            home_table = next((t["table"] for t in tables if t["type"] == "HOME"), [])
            away_table = next((t["table"] for t in tables if t["type"] == "AWAY"), [])
            
            standings_cache[comp_id] = {
                "total": {row["team"]["id"]: row for row in total_table},
                "home": {row["team"]["id"]: row for row in home_table},
                "away": {row["team"]["id"]: row for row in away_table}
            }

    filtered.sort(key=lambda x: x["utcDate"])
    mesajlar = []

    for match in filtered:
        status = match["status"]
        if status == "FINISHED":
            continue
            
        home_name = match["homeTeam"]["name"]
        away_name = match["awayTeam"]["name"]
        competition = match["competition"]["name"]
        utc_date = match["utcDate"][:16].replace("T", " ")
        
        home_id = match["homeTeam"]["id"]
        away_id = match["awayTeam"]["id"]
        comp_id = match["competition"]["id"]
        
        # Canlı maç kısmı
        is_live = status in ["LIVE", "IN_PLAY", "PAUSED"]
        if is_live:
            score = match.get("score", {}).get("fullTime", {})
            home_score = score.get("home", 0)
            away_score = score.get("away", 0)
            mesajlar.append(f"🔴 CANLI | {competition} | {home_name} {home_score}-{away_score} {away_name}")
            continue

        # Planlanmış Maçlar İçin Gelişmiş Analiz
        comp_data = standings_cache.get(comp_id)
        if not comp_data: continue

        total_home = comp_data["total"].get(home_id)
        total_away = comp_data["total"].get(away_id)
        home_stats = comp_data["home"].get(home_id)
        away_stats = comp_data["away"].get(away_id)

        # En az 2 maç oynanmış olmalı
        if not (home_stats and away_stats and total_home and total_away): continue
        if home_stats.get("playedGames", 0) < 2 or away_stats.get("playedGames", 0) < 2: continue

        # 1. İç/Dış Saha Maç Başına Puan (PPG)
        home_ppg = home_stats.get("points", 0) / home_stats["playedGames"]
        away_ppg = away_stats.get("points", 0) / away_stats["playedGames"]

        # 2. İç/Dış Saha Gol İstatistikleri
        home_gf = home_stats.get("goalsFor", 0) / home_stats["playedGames"]
        home_ga = home_stats.get("goalsAgainst", 0) / home_stats["playedGames"]
        away_gf = away_stats.get("goalsFor", 0) / away_stats["playedGames"]
        away_ga = away_stats.get("goalsAgainst", 0) / away_stats["playedGames"]

        # 3. Son 5 Maç Formu (Total tablodan)
        home_form_ppg = parse_form(total_home.get("form", ""))
        away_form_ppg = parse_form(total_away.get("form", ""))
        
        home_form_str = total_home.get("form", "Bilinmiyor").replace(",", "")
        away_form_str = total_away.get("form", "Bilinmiyor").replace(",", "")

        # 4. GÜÇ ALGORİTMASI HESAPLAMA
        # %40 Puan Ort. + %40 Form + %20 Averaj Farkı
        home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
        away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
        
        power_diff = home_power - away_power

        # 5. GOL ÇAPRAZLAMASI (Alt / Üst Tahmini)
        exp_home_goals = (home_gf + away_ga) / 2
        exp_away_goals = (away_gf + home_ga) / 2
        total_exp_goals = exp_home_goals + exp_away_goals

        # Karar Mekanizması
        ms_sinyal = ""
        ms_guven = ""
        if power_diff >= 0.8:
            ms_sinyal = "1️⃣ (Net Ev Sahibi)"
            ms_guven = "Yüksek"
        elif power_diff >= 0.4:
            ms_sinyal = "1️⃣ veya 1X"
            ms_guven = "Orta"
        elif power_diff <= -0.8:
            ms_sinyal = "2️⃣ (Net Deplasman)"
            ms_guven = "Yüksek"
        elif power_diff <= -0.4:
            ms_sinyal = "2️⃣ veya X2"
            ms_guven = "Orta"

        gol_sinyal = ""
        if total_exp_goals >= 3.0:
            gol_sinyal = "🔥 Üst 2.5 Güçlü"
        elif total_exp_goals <= 1.8:
            gol_sinyal = "🧊 Alt 2.5 Güçlü"

        # Eğer iki sinyalden (Taraf veya Gol) hiçbiri yoksa maçı atla (Kötü maç)
        if not ms_sinyal and not gol_sinyal:
            continue

        text = (
            f"🏆 {competition}\n"
            f"📅 {utc_date}\n"
            f"🏠 {home_name} (İç Saha Form: {home_form_str})\n"
            f"🚪 {away_name} (Dış Saha Form: {away_form_str})\n"
        )
        if ms_sinyal:
            text += f"🎯 Maç Sonucu: {ms_sinyal} (Güven: {ms_guven})\n"
        if gol_sinyal:
            text += f"⚽ Gol Tahmini: {gol_sinyal} (Bkl. Gol: {total_exp_goals:.1f})\n"
            
        text += f"📊 Güç Farkı: {power_diff:.2f}\n"
        mesajlar.append(text)

    if not mesajlar:
        await update.message.reply_text("İstatistiksel filtreden geçebilen Yüksek/Orta güvenli maç bulunamadı.")
    else:
        full_text = "\n────────────────────\n".join(mesajlar)
        if len(full_text) > 4000:
            for i in range(0, len(full_text), 4000):
                await update.message.reply_text(full_text[i:i+4000])
        else:
            await update.message.reply_text(full_text)

async def canli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maclar(update, context)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("canli", canli))
    
    print("Gelişmiş Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
