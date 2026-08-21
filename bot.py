import os
import requests
import traceback
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
APISPORTS_TOKEN = os.getenv("APISPORTS_TOKEN") # Basketbol için yeni token
headers_football = {"X-Auth-Token": FOOTBALL_TOKEN}

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
        "Avrupa Ligleri ve Basketbol Test Botu devrede! 🤖\n\n"
        "/maclar - Futbol maçlarını analiz eder\n"
        "/basket - Basketbol API'sini test eder"
    )

# --- BASKETBOL TEST KOMUTU ---
async def basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not APISPORTS_TOKEN:
        await update.message.reply_text("⚠️ APISPORTS_TOKEN bulunamadı. Lütfen Railway'e ekleyin.")
        return

    await update.message.reply_text("🏀 Basketbol API'si test ediliyor, lütfen bekle...")
    
    try:
        headers_basket = {"x-apisports-key": APISPORTS_TOKEN}
        today = datetime.utcnow().date().strftime("%Y-%m-%d")
        
        # Sadece test amaçlı bugünün maçlarını çekiyoruz
        url = f"https://v1.basketball.api-sports.io/games?date={today}"
        response = requests.get(url, headers=headers_basket)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ API Bağlantı Hatası: {response.status_code}")
            return
            
        data = response.json()
        errors = data.get("errors", {})
        
        if errors:
            await update.message.reply_text(f"⚠️ API-SPORTS BASKETBOL HATASI:\n{errors}")
            return
            
        games = data.get("response", [])
        if not games:
            await update.message.reply_text(f"ℹ️ Bugün ({today}) için basketbol maçı bulunamadı. (Farklı bir tarihte test gerekebilir)")
            return
            
        mesaj = f"✅ HARİKA! Basketbol API çalışıyor ve kısıtlama yok. Bugün {len(games)} maç bulundu.\n\nÖrnek Bir Maç:\n"
        ornek_mac = games[0]
        home = ornek_mac.get("teams", {}).get("home", {}).get("name", "Bilinmiyor")
        away = ornek_mac.get("teams", {}).get("away", {}).get("name", "Bilinmiyor")
        lig = ornek_mac.get("league", {}).get("name", "Bilinmeyen Lig")
        
        mesaj += f"🏆 {lig}\n🏀 {home} - {away}"
        
        await update.message.reply_text(mesaj)
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Hata oluştu:\n{str(e)}")

# --- FUTBOL ANA KOMUTU (Eski Haliyle Kusursuz Çalışmaya Devam Eder) ---
async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Futbol maçları analiz ediliyor...")
    
    try:
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=7)
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
        response = requests.get(url, headers=headers_football)
        
        if response.status_code == 429:
            await update.message.reply_text("⚠️ Hız sınırına takıldık. 1 dakika bekleyin.")
            return
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Veri alınamadı. API hatası: {response.status_code}")
            return
            
        matches = response.json().get("matches", [])
        filtered = [m for m in matches if any(l.lower() in m.get("competition", {}).get("name", "").lower() for l in ISTENEN_LIGLER)]
        
        if not filtered:
            await update.message.reply_text("Önümüzdeki 7 günde belirtilen liglerde futbol maçı bulunamadı.")
            return

        competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
        standings_cache = {}
        
        for comp_id in competitions:
            r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers_football)
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
            if status == "FINISHED": continue
                
            home_name = match.get("homeTeam", {}).get("name", "Ev Sahibi")
            away_name = match.get("awayTeam", {}).get("name", "Deplasman")
            competition = match.get("competition", {}).get("name", "")
            utc_date = match.get("utcDate", "")[:16].replace("T", " ")
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            comp_id = match.get("competition", {}).get("id")
            
            is_live = status in ["LIVE", "IN_PLAY", "PAUSED"]
            if is_live: continue # Canlıları atlıyoruz listeyi uzatmamak için

            comp_data = standings_cache.get(comp_id)
            if not comp_data: continue

            total_home = comp_data["total"].get(home_id) or {}
            total_away = comp_data["total"].get(away_id) or {}
            if not total_home or not total_away: continue
                
            home_stats = comp_data["home"].get(home_id) or total_home
            away_stats = comp_data["away"].get(away_id) or total_away
            
            t_h_played = total_home.get("playedGames", 0)
            t_a_played = total_away.get("playedGames", 0)
            if t_h_played == 0 or t_a_played == 0: continue

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
            
            home_form_raw = total_home.get("form")
            away_form_raw = total_away.get("form")
            home_form_ppg = parse_form(home_form_raw)
            away_form_ppg = parse_form(away_form_raw)
            home_form_str = str(home_form_raw).replace(",", "") if home_form_raw else "?"
            away_form_str = str(away_form_raw).replace(",", "") if away_form_raw else "?"

            home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
            power_diff = home_power - away_power
            total_exp_goals = (home_gf + away_ga) / 2 + (away_gf + home_ga) / 2

            ms_sinyal = ""
            if power_diff >= 0.7: ms_sinyal = "1️⃣ (Net Ev Sahibi) (Yüksek)"
            elif power_diff >= 0.3: ms_sinyal = "1️⃣ veya 1X (Orta)"
            elif power_diff <= -0.7: ms_sinyal = "2️⃣ (Net Deplasman) (Yüksek)"
            elif power_diff <= -0.3: ms_sinyal = "2️⃣ veya X2 (Orta)"

            gol_sinyal = ""
            if total_exp_goals >= 2.8: gol_sinyal = "🔥 Üst 2.5 Güçlü"
            elif total_exp_goals <= 1.8: gol_sinyal = "🧊 Alt 2.5 Güçlü"

            if ms_sinyal or gol_sinyal:
                text = f"🏆 {competition}\n📅 {utc_date}\n🏠 {home_name} (Form: {home_form_str})\n🚪 {away_name} (Form: {away_form_str})\n"
                if ms_sinyal: text += f"🎯 MS: {ms_sinyal}\n"
                if gol_sinyal: text += f"⚽ Gol: {gol_sinyal} (Bkl: {total_exp_goals:.1f})\n"
                text += f"📊 Güç Farkı: {power_diff:.2f}\n"
                mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text("Şu an analiz edilebilir futbol maçı yok.")
        else:
            full_text = "\n────────────────────\n".join(mesajlar)
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    await update.message.reply_text(full_text[i:i+4000])
            else:
                await update.message.reply_text(full_text)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Futbol hatası:\n{str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("basket", basket))
    print("Bot Başladı (Futbol + Basketbol Test)")
    app.run_polling()

if __name__ == "__main__":
    main()
