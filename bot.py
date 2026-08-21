import os
import requests
import traceback
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
headers = {"X-Auth-Token": FOOTBALL_TOKEN}

ISTENEN_LIGLER = [
    "Premier League", "Primera Division", "Serie A",
    "Bundesliga", "Ligue 1", "UEFA Champions League", "Champions League"
]

def parse_form(form_str):
    if not form_str:
        return 1.0  
    form_str = str(form_str).replace(",", "").replace(" ", "").upper()
    pts = sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str)
    return pts / len(form_str) if len(form_str) > 0 else 1.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Avrupa Ligleri Gelişmiş Analiz Botu devrede! 🤖\n\n/maclar - Analizli maçları getirir"
    )

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Maçlar analiz ediliyor, lütfen bekle...")
    
    try:
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=7)
        
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:
            await update.message.reply_text("⚠️ Hız sınırına takıldık (Dakikada 10 istek). Lütfen 1 dakika bekleyip tekrar dene.")
            return
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Veri alınamadı. API hatası: {response.status_code}")
            return
            
        matches = response.json().get("matches", [])
        filtered = [m for m in matches if any(l.lower() in m.get("competition", {}).get("name", "").lower() for l in ISTENEN_LIGLER)]
        
        if not filtered:
            await update.message.reply_text("Önümüzdeki 7 günde belirtilen liglerde maç bulunamadı.")
            return

        competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
        standings_cache = {}
        
        for comp_id in competitions:
            r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers)
            if r.status_code == 429:
                await update.message.reply_text("⚠️ Puan durumu çekilirken hız sınırına (429) takıldık. 1 dk bekle.")
                return
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

        filtered.sort(key=lambda x: x.get("utcDate", ""))
        mesajlar = []

        for match in filtered:
            status = match.get("status", "")
            if status == "FINISHED":
                continue
                
            home_name = match.get("homeTeam", {}).get("name", "Bilinmeyen Ev Sahibi")
            away_name = match.get("awayTeam", {}).get("name", "Bilinmeyen Deplasman")
            competition = match.get("competition", {}).get("name", "")
            utc_date = match.get("utcDate", "")[:16].replace("T", " ")
            
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            comp_id = match.get("competition", {}).get("id")
            
            is_live = status in ["LIVE", "IN_PLAY", "PAUSED"]
            if is_live:
                score = match.get("score") or {}
                full_time = score.get("fullTime") or {}
                home_score = full_time.get("home") or 0
                away_score = full_time.get("away") or 0
                mesajlar.append(f"🔴 CANLI | {competition} | {home_name} {home_score}-{away_score} {away_name}")
                continue

            comp_data = standings_cache.get(comp_id)
            if not comp_data:
                continue

            total_home = comp_data["total"].get(home_id) or {}
            total_away = comp_data["total"].get(away_id) or {}

            if not total_home or not total_away:
                continue
                
            home_stats = comp_data["home"].get(home_id) or total_home
            away_stats = comp_data["away"].get(away_id) or total_away
            
            t_h_played = total_home.get("playedGames", 0)
            t_a_played = total_away.get("playedGames", 0)
            
            if t_h_played == 0 or t_a_played == 0:
                mesajlar.append(f"🏆 {competition}\n📅 {utc_date}\n🏠 {home_name} - 🚪 {away_name}\n⚠️ Sezonun ilk maçı (Veri yok).\n")
                continue

            h_played = home_stats.get("playedGames", 0)
            a_played = away_stats.get("playedGames", 0)
            
            if h_played == 0:
                home_stats = total_home
                h_played = total_home.get("playedGames", 1)
            if a_played == 0:
                away_stats = total_away
                a_played = total_away.get("playedGames", 1)

            home_ppg = home_stats.get("points", 0) / h_played
            away_ppg = away_stats.get("points", 0) / a_played

            home_gf = home_stats.get("goalsFor", 0) / h_played
            home_ga = home_stats.get("goalsAgainst", 0) / h_played
            away_gf = away_stats.get("goalsFor", 0) / a_played
            away_ga = away_stats.get("goalsAgainst", 0) / a_played

            home_form_ppg = parse_form(total_home.get("form", ""))
            away_form_ppg = parse_form(total_away.get("form", ""))
            
            home_form_str = str(total_home.get("form", "?")).replace(",", "")
            away_form_str = str(total_away.get("form", "?")).replace(",", "")

            home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
            
            power_diff = home_power - away_power
            total_exp_goals = (home_gf + away_ga) / 2 + (away_gf + home_ga) / 2

            ms_sinyal = ""
            ms_guven = ""
            
            if power_diff >= 0.7:
                ms_sinyal = "1️⃣ (Net Ev Sahibi)"
                ms_guven = "Yüksek"
            elif power_diff >= 0.3:
                ms_sinyal = "1️⃣ veya 1X"
                ms_guven = "Orta"
            elif power_diff <= -0.7:
                ms_sinyal = "2️⃣ (Net Deplasman)"
                ms_guven = "Yüksek"
            elif power_diff <= -0.3:
                ms_sinyal = "2️⃣ veya X2"
                ms_guven = "Orta"

            gol_sinyal = ""
            if total_exp_goals >= 2.8:
                gol_sinyal = "🔥 Üst 2.5 Güçlü"
            elif total_exp_goals <= 1.8:
                gol_sinyal = "🧊 Alt 2.5 Güçlü"

            if ms_sinyal or gol_sinyal:
                text = (
                    f"🏆 {competition}\n"
                    f"📅 {utc_date}\n"
                    f"🏠 {home_name} (Form: {home_form_str})\n"
                    f"🚪 {away_name} (Form: {away_form_str})\n"
                )
                if ms_sinyal:
                    text += f"🎯 MS: {ms_sinyal} (Güven: {ms_guven})\n"
                if gol_sinyal:
                    text += f"⚽ Gol: {gol_sinyal} (Bkl: {total_exp_goals:.1f})\n"
                    
                text += f"📊 Güç Farkı: {power_diff:.2f}\n"
                mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text("Şu an analiz edilebilir maç yok (Takımlar ya maça çıkmadı ya da güç dengeleri çok yakın).")
        else:
            full_text = "\n────────────────────\n".join(mesajlar)
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    await update.message.reply_text(full_text[i:i+4000])
            else:
                await update.message.reply_text(full_text)

    except Exception as e:
        error_details = traceback.format_exc()
        await update.message.reply_text(f"⚠️ Kritik bir hata oluştu ve bot durdu:\n\n{str(e)}\n\nLütfen bu mesajı bana gönder.")
        print(error_details)

async def canli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await maclar(update, context)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("canli", canli))
    
    print("football-data Botu (Güvenli Sürüm) Başladı...")
    app.run_polling()

if __name__ == "__main__":
    main()
