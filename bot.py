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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 Multi-Spor Kapsamlı Analiz Botu Devrede!\n\n"
        "Menüden istediğiniz sporu seçerek 'Galibiyet, Form ve Averaj' çaprazlamalı istatistiklere ulaşabilirsiniz."
    )

# ==========================================
# 🏐 Voleybol, 🏒 Hokey, 🤾 Hentbol İÇİN ORTAK API-SPORTS MOTORU
# ==========================================
async def apisports_analyzer(update: Update, sport_name: str, base_url: str, dev_leagues: list, icon: str):
    if not APISPORTS_TOKEN:
        await update.message.reply_text("⚠️ APISPORTS_TOKEN bulunamadı.")
        return

    await update.message.reply_text(f"{icon} {sport_name} maçları tüm kriterlere (Galibiyet + Form + Averaj) göre analiz ediliyor...")
    
    try:
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        dates_to_check = [today.strftime("%Y-%m-%d"), tomorrow.strftime("%Y-%m-%d")]
        
        all_games = []
        for d in dates_to_check:
            res = requests.get(f"{base_url}/games?date={d}", headers=headers_apisports)
            if res.status_code == 200:
                all_games.extend(res.json().get("response", []))
                
        filtered_games = [g for g in all_games if any(l.lower() in g.get("league", {}).get("name", "").lower() for l in dev_leagues)]
        
        if not filtered_games:
            await update.message.reply_text(f"ℹ️ Bugün ve yarın için seçili {sport_name} dev liglerinde maç bulunamadı.")
            return

        leagues = {(g["league"]["id"], g["league"]["season"]) for g in filtered_games}
        standings_cache = {}
        
        for lig_id, lig_sezon in leagues:
            std_res = requests.get(f"{base_url}/standings?league={lig_id}&season={lig_sezon}", headers=headers_apisports)
            if std_res.status_code == 200:
                standings_data = std_res.json().get("response", [])
                team_dict = {}
                for item in standings_data:
                    if isinstance(item, list):
                        for row in item:
                            t_id = row.get("team", {}).get("id")
                            if t_id: team_dict[t_id] = row
                    else:
                        t_id = item.get("team", {}).get("id")
                        if t_id: team_dict[t_id] = item
                standings_cache[lig_id] = team_dict

        mesajlar = []
        
        for game in filtered_games:
            status = game.get("status", {}).get("short", "")
            if status in ["FT", "AOT", "CANC", "POST", "LIVE", "IN_PLAY"]: continue
            
            lig_id = game["league"]["id"]
            lig_adi = game["league"]["name"]
            home_team = game["teams"]["home"]["name"]
            away_team = game["teams"]["away"]["name"]
            home_id = game["teams"]["home"]["id"]
            away_id = game["teams"]["away"]["id"]
            saat = game["date"][:16].replace("T", " ")
            
            comp_data = standings_cache.get(lig_id, {})
            home_stats = comp_data.get(home_id, {})
            away_stats = comp_data.get(away_id, {})
            
            h_games = home_stats.get("games", {})
            a_games = away_stats.get("games", {})
            h_played = h_games.get("played", 0)
            a_played = a_games.get("played", 0)
            
            if h_played < 1 or a_played < 1: continue
                
            h_win = (h_games.get("win") or h_games.get("won") or {}).get("total", 0)
            a_win = (a_games.get("win") or a_games.get("won") or {}).get("total", 0)
            
            # 1. Kriter: Galibiyet Yüzdesi
            home_win_rate = h_win / h_played
            away_win_rate = a_win / a_played
            
            # 2. Kriter: Skor/Set Averajı
            # Voleybolda set averajı, Hokeyde gol, Basketbolda sayı averajı
            h_pts = home_stats.get("goals") or home_stats.get("points") or {}
            a_pts = away_stats.get("goals") or away_stats.get("points") or {}
            
            home_for = h_pts.get("for", 0) / h_played
            home_against = h_pts.get("against", 0) / h_played
            away_for = a_pts.get("for", 0) / a_played
            away_against = a_pts.get("against", 0) / a_played
            
            h_averaj_katsayisi = home_for - home_against
            a_averaj_katsayisi = away_for - away_against
            
            # 3. Kriter: Form Durumu
            home_form_raw = home_stats.get("form", "?")
            away_form_raw = away_stats.get("form", "?")
            home_form_val = parse_form(home_form_raw)
            away_form_val = parse_form(away_form_raw)
            
            # KAPSAMLI GÜÇ HESAPLAMASI (%50 Galibiyet, %30 Form, %20 Averaj)
            # Averajı normalize etmek için 0.1 ile çarpıyoruz (uçurum olmaması için)
            home_power = (home_win_rate * 0.5) + (home_form_val * 0.3) + (h_averaj_katsayisi * 0.1)
            away_power = (away_win_rate * 0.5) + (away_form_val * 0.3) + (a_averaj_katsayisi * 0.1)
            
            power_diff = home_power - away_power
            exp_total = (home_for + away_against)/2 + (away_for + home_against)/2
            
            ms_sinyal = ""
            if power_diff >= 0.50: ms_sinyal = "1️⃣ (Net Ev Sahibi) (Yüksek)"
            elif power_diff >= 0.25: ms_sinyal = "1️⃣ (Ev Sahibi Avantajlı) (Orta)"
            elif power_diff <= -0.50: ms_sinyal = "2️⃣ (Net Deplasman) (Yüksek)"
            elif power_diff <= -0.25: ms_sinyal = "2️⃣ (Deplasman Avantajlı) (Orta)"

            if ms_sinyal:
                text = (
                    f"🏆 {lig_adi}\n📅 {saat}\n"
                    f"🏠 {home_team} (Form: {str(home_form_raw).replace(',','')})\n"
                    f"🚪 {away_team} (Form: {str(away_form_raw).replace(',','')})\n"
                    f"🎯 MS: {ms_sinyal}\n"
                    f"📊 Kapsamlı Güç Farkı: {power_diff:.2f}\n"
                    f"⚙️ Beklenen Toplam (Sayı/Gol/Set): {exp_total:.1f}"
                )
                mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text(f"Şu an analiz edilebilir durumda {sport_name} maçı yok.")
        else:
            full_text = "\n────────────────────\n".join(mesajlar)
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    await update.message.reply_text(full_text[i:i+4000])
            else:
                await update.message.reply_text(full_text)

    except Exception as e:
        await update.message.reply_text(f"⚠️ {sport_name} analizinde hata:\n{str(e)}")

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

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(setup_menu).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("basket", basket))
    app.add_handler(CommandHandler("voleybol", voleybol))
    app.add_handler(CommandHandler("hokey", hokey))
    app.add_handler(CommandHandler("hentbol", hentbol))
    
    print("Multi-Spor Kapsamlı Botu Başladı...")
    app.run_polling()

if __name__ == "__main__":
    main()
