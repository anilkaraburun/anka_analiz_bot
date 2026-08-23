import os
import requests
import traceback
from datetime import datetime, timedelta
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
APISPORTS_TOKEN = os.getenv("APISPORTS_TOKEN")

headers_football = {"X-Auth-Token": FOOTBALL_TOKEN}
headers_apisports = {"x-apisports-key": APISPORTS_TOKEN}

ISTENEN_FUTBOL_LIGLERI = ["Premier League", "Primera Division", "Serie A", "Bundesliga", "Ligue 1", "UEFA Champions League"]
ISTENEN_BASKET_LIGLERI = ["NBA", "WNBA", "Euroleague", "Super Lig", "BSL", "Liga ACB"]
ISTENEN_VOLEYBOL_LIGLERI = ["SuperLega", "PlusLiga", "Efeler Ligi", "Sultanlar Ligi", "Champions League"]
ISTENEN_HOKEY_LIGLERI = ["NHL", "KHL", "SHL", "Liiga"]
ISTENEN_HENTBOL_LIGLERI = ["Champions League", "Bundesliga", "LNH Division 1"]

# Form (WWDL) hesaplama (Tüm sporlar için ortak)
def parse_form(form_str):
    if not form_str: return 1.0  
    form_str = str(form_str).replace(",", "").replace(" ", "").upper()
    pts = sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str)
    return pts / len(form_str) if len(form_str) > 0 else 1.0

# ==========================================
# ⚙️ OTOMATİK MENÜ KURULUMU
# ==========================================
# ==========================================
# ⚽ FUTBOL ANALİZ ALGORİTMASI (football-data.org)
# ==========================================
async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Futbol maçları analiz ediliyor, lütfen bekle...")
    try:
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=7)
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
        response = requests.get(url, headers=headers_football)

        if response.status_code == 429:
            await update.message.reply_text("⚠️ Hız sınırına takıldık (Dakikada 10 istek). Lütfen 1 dakika bekleyip tekrar dene.")
            return
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Futbol API hatası: {response.status_code}")
            return

        matches = response.json().get("matches", [])
        filtered = [m for m in matches if any(l.lower() in m.get("competition", {}).get("name", "").lower() for l in ISTENEN_FUTBOL_LIGLERI)]

        if not filtered:
            await update.message.reply_text("Önümüzdeki 7 günde belirtilen liglerde maç bulunamadı.")
            return

        competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
        standings_cache = {}
        for comp_id in competitions:
            r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers_football)

            if r.status_code == 429:
                await update.message.reply_text("⚠️ Puan durumu çekilirken hız sınırına (429) takıldık. 1 dakika bekleyip tekrar dene.")
                return
            if r.status_code != 200:
                continue

            tables = r.json().get("standings", [])
            standings_cache[comp_id] = {
                "total": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "TOTAL"), [])},
                "home": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "HOME"), [])},
                "away": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "AWAY"), [])}
            }

        mesajlar = []
        for match in filtered:
            status = match.get("status", "")
            if status in ["FINISHED", "LIVE", "IN_PLAY", "PAUSED"]:
                continue

            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            comp_id = match.get("competition", {}).get("id")

            comp_data = standings_cache.get(comp_id)
            if not comp_data:
                continue
            total_home = comp_data["total"].get(home_id) or {}
            total_away = comp_data["total"].get(away_id) or {}
            if not total_home or not total_away:
                continue

            home_stats = comp_data["home"].get(home_id) or total_home
            away_stats = comp_data["away"].get(away_id) or total_away
            if total_home.get("playedGames", 0) == 0 or total_away.get("playedGames", 0) == 0:
                continue

            h_played = home_stats.get("playedGames", 1)
            a_played = away_stats.get("playedGames", 1)

            home_ppg = home_stats.get("points", 0) / h_played
            away_ppg = away_stats.get("points", 0) / a_played
            home_gf = home_stats.get("goalsFor", 0) / h_played
            home_ga = home_stats.get("goalsAgainst", 0) / h_played
            away_gf = away_stats.get("goalsFor", 0) / a_played
            away_ga = away_stats.get("goalsAgainst", 0) / a_played

            home_form_ppg = parse_form(total_home.get("form"))
            away_form_ppg = parse_form(total_away.get("form"))

            home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
            power_diff = home_power - away_power

            total_exp_goals = (home_gf + away_ga) / 2 + (away_gf + home_ga) / 2

            ms_sinyal = ""
            if power_diff >= 0.7:
                ms_sinyal = "1️⃣ (Net Ev Sahibi)"
            elif power_diff >= 0.3:
                ms_sinyal = "1️⃣ veya 1X"
            elif power_diff <= -0.7:
                ms_sinyal = "2️⃣ (Net Deplasman)"
            elif power_diff <= -0.3:
                ms_sinyal = "2️⃣ veya X2"

            gol_sinyal = ""
            if total_exp_goals >= 2.6:
                gol_sinyal = "🔥 Üst 2.5"
            elif total_exp_goals <= 2.0:
                gol_sinyal = "🧊 Alt 2.5"

            if ms_sinyal or gol_sinyal:
                text = (
                    f"🏆 {match['competition']['name']}\n📅 {match['utcDate'][:16].replace('T', ' ')}\n"
                    f"🏠 {match['homeTeam']['name']} (Form: {str(total_home.get('form', '?')).replace(',', '')})\n"
                    f"🚪 {match['awayTeam']['name']} (Form: {str(total_away.get('form', '?')).replace(',', '')})\n"
                )
                if ms_sinyal:
                    text += f"🎯 MS: {ms_sinyal}\n"
                if gol_sinyal:
                    text += f"⚽ Gol: {gol_sinyal} (Bkl: {total_exp_goals:.1f})\n"
                text += f"📊 Güç Farkı: {power_diff:.2f}\n"
                mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text("Şu an analiz edilebilir futbol maçı yok.")
        else:
            full_text = "\n────────────────────\n".join(mesajlar)
            for i in range(0, len(full_text), 4000):
                await update.message.reply_text(full_text[i:i + 4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ Futbol analizinde hata:\n{str(e)}")
# ==========================================
# KOMUT YÖNLENDİRİCİLERİ
# ==========================================
async def basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Basketbol", "https://v1.basketball.api-sports.io", ISTENEN_BASKET_LIGLERI, "🏀")

async def voleybol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Voleybol", "https://v1.volleyball.api-sports.io", ISTENEN_VOLEYBOL_LIGLERI, "🏐")

async def hokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Buz Hokeyi", "https://v1.hockey.api-sports.io", ISTENEN_HOKEY_LIGLERI, "🏒")

async def hentbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Hentbol", "https://v1.handball.api-sports.io", ISTENEN_HENTBOL_LIGLERI, "🤾")

# ==========================================
# ⚽ FUTBOL ANALİZ ALGORİTMASI (football-data.org)
# ==========================================
async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Futbol maçları analiz ediliyor, lütfen bekle...")
    try:
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=7)
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
        response = requests.get(url, headers=headers_football)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Futbol API hatası: {response.status_code}")
            return
            
        matches = response.json().get("matches", [])
        filtered = [m for m in matches if any(l.lower() in m.get("competition", {}).get("name", "").lower() for l in ISTENEN_FUTBOL_LIGLERI)]
        
        if not filtered:
            await update.message.reply_text("Önümüzdeki 7 günde belirtilen liglerde maç bulunamadı.")
            return

        competitions = {m["competition"]["id"]: m["competition"]["name"] for m in filtered}
        standings_cache = {}
        for comp_id in competitions:
            r = requests.get(f"https://api.football-data.org/v4/competitions/{comp_id}/standings", headers=headers_football)
            if r.status_code == 200:
                tables = r.json().get("standings", [])
                standings_cache[comp_id] = {
                    "total": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "TOTAL"), [])},
                    "home": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "HOME"), [])},
                    "away": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "AWAY"), [])}
                }

        mesajlar = []
        for match in filtered:
            status = match.get("status", "")
            if status in ["FINISHED", "LIVE", "IN_PLAY", "PAUSED"]: continue
                
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            comp_id = match.get("competition", {}).get("id")
            
            comp_data = standings_cache.get(comp_id)
            if not comp_data: continue
            total_home = comp_data["total"].get(home_id) or {}
            total_away = comp_data["total"].get(away_id) or {}
            if not total_home or not total_away: continue
                
            home_stats = comp_data["home"].get(home_id) or total_home
            away_stats = comp_data["away"].get(away_id) or total_away
            if total_home.get("playedGames", 0) == 0 or total_away.get("playedGames", 0) == 0: continue

            h_played = home_stats.get("playedGames", 1)
            a_played = away_stats.get("playedGames", 1)

            home_ppg = home_stats.get("points", 0) / h_played
            away_ppg = away_stats.get("points", 0) / a_played
            home_gf = home_stats.get("goalsFor", 0) / h_played
            home_ga = home_stats.get("goalsAgainst", 0) / h_played
            away_gf = away_stats.get("goalsFor", 0) / a_played
            away_ga = away_stats.get("goalsAgainst", 0) / a_played
            
            home_form_ppg = parse_form(total_home.get("form"))
            away_form_ppg = parse_form(total_away.get("form"))

            home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
            power_diff = home_power - away_power

            ms_sinyal = ""
            if power_diff >= 0.7: ms_sinyal = "1️⃣ (Net Ev Sahibi)"
            elif power_diff >= 0.3: ms_sinyal = "1️⃣ veya 1X"
            elif power_diff <= -0.7: ms_sinyal = "2️⃣ (Net Deplasman)"
            elif power_diff <= -0.3: ms_sinyal = "2️⃣ veya X2"

            if ms_sinyal:
                mesajlar.append(
                    f"🏆 {match['competition']['name']}\n📅 {match['utcDate'][:16].replace('T', ' ')}\n"
                    f"🏠 {match['homeTeam']['name']} (Form: {str(total_home.get('form', '?')).replace(',','')})\n"
                    f"🚪 {match['awayTeam']['name']} (Form: {str(total_away.get('form', '?')).replace(',','')})\n"
                    f"🎯 MS: {ms_sinyal}\n📊 Güç Farkı: {power_diff:.2f}\n"
                )

        if not mesajlar: await update.message.reply_text("Şu an analiz edilebilir futbol maçı yok.")
        else: await update.message.reply_text("\n────────────────────\n".join(mesajlar)[:4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ Futbol analizinde hata:\n{str(e)}")

async def setup_menu(application: Application):
    commands = [
        BotCommand("start", "🤖 Botu başlatır"),
        BotCommand("maclar", "⚽ Futbol (Form+Gol)"),
        BotCommand("basket", "🏀 Basketbol (Kapsamlı)"),
        BotCommand("voleybol", "🏐 Voleybol (Set+Form)"),
        BotCommand("hokey", "🏒 Buz Hokeyi (Gol+Form)"),
        BotCommand("hentbol", "🤾 Hentbol (Sayı+Form)")
    ]
    await application.bot.set_my_commands(commands)
    print("Multi-Spor Menüsü Telegram'a yüklendi!")

if __name__ == "__main__":
    main()
