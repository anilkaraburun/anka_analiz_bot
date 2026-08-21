import os
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}

LEAGUES = {
    203: "🇹🇷 Süper Lig",
    39: "🇬🇧 Premier League",
    140: "🇪🇸 La Liga",
    135: "🇮🇹 Serie A",
    78: "🇩🇪 Bundesliga",
    61: "🇫🇷 Ligue 1"
}

def parse_form(form_str):
    if not form_str:
        return 1.0  
    form_str = str(form_str).upper()
    pts = sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str)
    return pts / len(form_str) if len(form_str) > 0 else 1.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Filtresiz Analiz Modu aktif. 🤖\n/maclar - Tüm maçları getirir")

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tüm maçlar (filtresiz) çekiliyor, bekle...")
    
    today = datetime.utcnow()
    season = today.year if today.month >= 7 else today.year - 1
    
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    
    standings_cache = {}
    mesajlar = []
    
    for comp_id, comp_name in LEAGUES.items():
        std_url = f"{API_URL}/standings?league={comp_id}&season={season}"
        std_req = requests.get(std_url, headers=HEADERS)
        
        standings_cache[comp_id] = {}
        if std_req.status_code == 200 and std_req.json().get("response"):
            league_data = std_req.json()["response"][0]["league"]
            for group in league_data.get("standings", []):
                for row in group:
                    team_id = row["team"]["id"]
                    standings_cache[comp_id][team_id] = row
                    
        fix_url = f"{API_URL}/fixtures?league={comp_id}&season={season}&from={start_date}&to={end_date}"
        fix_req = requests.get(fix_url, headers=HEADERS)
        
        if fix_req.status_code != 200:
            continue
            
        fixtures = fix_req.json().get("response", [])
        
        for match in fixtures:
            status = match["fixture"]["status"]["short"]
            
            if status in ["FT", "AET", "PEN", "CANC", "PST", "ABD"]:
                continue
                
            home_team = match["teams"]["home"]["name"]
            away_team = match["teams"]["away"]["name"]
            utc_date = match["fixture"]["date"][:16].replace("T", " ")
            home_id = match["teams"]["home"]["id"]
            away_id = match["teams"]["away"]["id"]
            
            is_live = status in ["1H", "2H", "HT", "ET", "BT", "P", "LIVE"]
            if is_live:
                h_score = match["goals"]["home"] if match["goals"]["home"] is not None else 0
                a_score = match["goals"]["away"] if match["goals"]["away"] is not None else 0
                mesajlar.append(f"🔴 CANLI | {comp_name} | {home_team} {h_score}-{a_score} {away_team}")
                continue

            if status != "NS":
                continue
                
            home_stats = standings_cache[comp_id].get(home_id)
            away_stats = standings_cache[comp_id].get(away_id)
            
            if not (home_stats and away_stats):
                continue
                
            home_record = home_stats.get("all", {})
            away_record = away_stats.get("all", {})
            
            h_played = home_record.get("played", 0)
            a_played = away_record.get("played", 0)
            
            if h_played < 1 or a_played < 1:
                mesajlar.append(f"🏆 {comp_name}\n📅 {utc_date}\n🏠 {home_team} - 🚪 {away_team}\n⚠️ Yeterli veri yok (Henüz maça çıkmamışlar)\n")
                continue
                
            h_win = home_record.get("win", 0)
            h_draw = home_record.get("draw", 0)
            a_win = away_record.get("win", 0)
            a_draw = away_record.get("draw", 0)
            
            home_ppg = ((h_win * 3) + h_draw) / h_played
            away_ppg = ((a_win * 3) + a_draw) / a_played
            
            home_gf = home_record.get("goals", {}).get("for", 0) / h_played
            home_ga = home_record.get("goals", {}).get("against", 0) / h_played
            away_gf = away_record.get("goals", {}).get("for", 0) / a_played
            away_ga = away_record.get("goals", {}).get("against", 0) / a_played
            
            home_form_str = home_stats.get("form", "") or "?"
            away_form_str = away_stats.get("form", "") or "?"
            
            home_power = (home_ppg * 0.4) + (parse_form(home_form_str) * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (parse_form(away_form_str) * 0.4) + ((away_gf - away_ga) * 0.2)
            
            power_diff = home_power - away_power
            total_exp_goals = ((home_gf + away_ga) / 2) + ((away_gf + home_ga) / 2)
            
            ms_sinyal = "Belirsiz (İzleyin)"
            ms_guven = "Düşük"
            
            if power_diff >= 0.6:
                ms_sinyal = "1️⃣"
                ms_guven = "Yüksek"
            elif power_diff >= 0.2:
                ms_sinyal = "1️⃣ veya 1X"
                ms_guven = "Orta"
            elif power_diff <= -0.6:
                ms_sinyal = "2️⃣"
                ms_guven = "Yüksek"
            elif power_diff <= -0.2:
                ms_sinyal = "2️⃣ veya X2"
                ms_guven = "Orta"
                
            gol_sinyal = "Kararsız"
            if total_exp_goals >= 2.6:
                gol_sinyal = "Üst 2.5"
            elif total_exp_goals <= 2.0:
                gol_sinyal = "Alt 2.5"
                
            text = (
                f"🏆 {comp_name}\n"
                f"📅 {utc_date}\n"
                f"🏠 {home_team} ({home_form_str})\n"
                f"🚪 {away_team} ({away_form_str})\n"
                f"🎯 MS: {ms_sinyal} ({ms_guven})\n"
                f"⚽ Gol: {gol_sinyal} ({total_exp_goals:.1f})\n"
                f"📊 Güç Farkı: {power_diff:.2f}\n"
            )
            mesajlar.append(text)

    if not mesajlar:
        await update.message.reply_text("Hiç maç bulunamadı. Veri çekme aşamasında bir sorun var.")
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
    print("Bot Filtresiz Modda Başladı...")
    app.run_polling()

if __name__ == "__main__":
    main()
