import os
import requests
import traceback
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
APISPORTS_TOKEN = os.getenv("APISPORTS_TOKEN")

headers_football = {"X-Auth-Token": FOOTBALL_TOKEN}
headers_basket = {"x-apisports-key": APISPORTS_TOKEN}

ISTENEN_FUTBOL_LIGLERI = [
    "Premier League", "Primera Division", "Serie A",
    "Bundesliga", "Ligue 1", "UEFA Champions League", "Champions League"
]

ISTENEN_BASKET_LIGLERI = ["NBA", "WNBA", "Euroleague", "Super Lig", "BSL", "Liga ACB"]

def parse_form(form_str):
    if not form_str: return 1.0  
    form_str = str(form_str).replace(",", "").replace(" ", "").upper()
    pts = sum(3 if c == 'W' else 1 if c == 'D' else 0 for c in form_str)
    return pts / len(form_str) if len(form_str) > 0 else 1.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Avrupa Futbol ve Basketbol Analiz Botu Devrede! 🤖\n\n"
        "⚽ /maclar - Futbol maçlarını analiz eder\n"
        "🏀 /basket - Basketbol maçlarını analiz eder"
    )

# ==========================================
# 🏀 BASKETBOL ANALİZ ALGORİTMASI
# ==========================================
async def basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not APISPORTS_TOKEN:
        await update.message.reply_text("⚠️ APISPORTS_TOKEN bulunamadı.")
        return

    await update.message.reply_text("🏀 Tüm konferanslar ve veriler taranıyor, lütfen bekle...")
    
    try:
        today = datetime.utcnow().date()
        tomorrow = today + timedelta(days=1)
        dates_to_check = [today.strftime("%Y-%m-%d"), tomorrow.strftime("%Y-%m-%d")]
        
        all_games = []
        for d in dates_to_check:
            res = requests.get(f"https://v1.basketball.api-sports.io/games?date={d}", headers=headers_basket)
            if res.status_code == 200:
                all_games.extend(res.json().get("response", []))
                
        filtered_games = [g for g in all_games if any(l.lower() in g.get("league", {}).get("name", "").lower() for l in ISTENEN_BASKET_LIGLERI)]
        
        if not filtered_games:
            await update.message.reply_text("ℹ️ Bugün ve yarın için seçili dev liglerde basketbol maçı bulunamadı.")
            return

        leagues = {(g["league"]["id"], g["league"]["season"]) for g in filtered_games}
        standings_cache = {}
        
        for lig_id, lig_sezon in leagues:
            std_res = requests.get(f"https://v1.basketball.api-sports.io/standings?league={lig_id}&season={lig_sezon}", headers=headers_basket)
            if std_res.status_code == 200:
                standings_data = std_res.json().get("response", [])
                team_dict = {}
                
                # Tüm konferansları (Doğu/Batı) veya Grupları dolaş
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
            if status in ["FT", "AOT", "CANC", "POST"]: continue
            
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
            
            # Veri yoksa pas geç, ekranı kirletme
            if h_played < 1 or a_played < 1:
                continue
                
            # API'nin "win" veya "won" kullanımını garantiye al
            h_win_data = h_games.get("win") or h_games.get("won") or {}
            a_win_data = a_games.get("win") or a_games.get("won") or {}
            
            h_win = h_win_data.get("total", 0)
            a_win = a_win_data.get("total", 0)
            
            home_win_rate = h_win / h_played
            away_win_rate = a_win / a_played
            
            h_pts = home_stats.get("points", {})
            a_pts = away_stats.get("points", {})
            
            home_pf = h_pts.get("for", 0) / h_played
            home_pa = h_pts.get("against", 0) / h_played
            away_pf = a_pts.get("for", 0) / a_played
            away_pa = a_pts.get("against", 0) / a_played
            
            exp_home_pts = (home_pf + away_pa) / 2
            exp_away_pts = (away_pf + home_pa) / 2
            total_exp_pts = exp_home_pts + exp_away_pts
            
            power_diff = home_win_rate - away_win_rate
            
            ms_sinyal = ""
            ms_guven = ""
            
            if power_diff >= 0.40:
                ms_sinyal = "1️⃣ (Net Ev Sahibi)"
                ms_guven = "Yüksek"
            elif power_diff >= 0.20:
                ms_sinyal = "1️⃣ (Ev Sahibi Avantajlı)"
                ms_guven = "Orta"
            elif power_diff <= -0.40:
                ms_sinyal = "2️⃣ (Net Deplasman)"
                ms_guven = "Yüksek"
            elif power_diff <= -0.20:
                ms_sinyal = "2️⃣ (Deplasman Avantajlı)"
                ms_guven = "Orta"

            text = (
                f"🏆 {lig_adi}\n📅 {saat}\n"
                f"🏠 {home_team} (Galibiyet: %{int(home_win_rate*100)})\n"
                f"🚪 {away_team} (Galibiyet: %{int(away_win_rate*100)})\n"
            )
            if ms_sinyal:
                text += f"🎯 MS: {ms_sinyal} (Güven: {ms_guven})\n"
                
            text += f"🏀 Beklenen Toplam Sayı: {total_exp_pts:.1f} (Ev: {exp_home_pts:.1f} - Dep: {exp_away_pts:.1f})\n"
            text += f"📊 Güç Farkı (Yüzde): {power_diff:.2f}\n"
            
            mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text("Bugün ve yarın için analiz edilebilir durumda basketbol maçı yok (veya güçler çok yakın).")
        else:
            full_text = "\n────────────────────\n".join(mesajlar)
            if len(full_text) > 4000:
                for i in range(0, len(full_text), 4000):
                    await update.message.reply_text(full_text[i:i+4000])
            else:
                await update.message.reply_text(full_text)

    except Exception as e:
        error_details = traceback.format_exc()
        await update.message.reply_text(f"⚠️ Basketbol analizinde hata oluştu:\n{str(e)}")
        print(error_details)

# ==========================================
# ⚽ FUTBOL ANALİZ ALGORİTMASI
# ==========================================
async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Futbol maçları analiz ediliyor, lütfen bekle...")
    
    try:
        today = datetime.utcnow().date()
        end_date = today + timedelta(days=7)
        
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end_date}"
        response = requests.get(url, headers=headers_football)
        
        if response.status_code == 429:
            await update.message.reply_text("⚠️ Hız sınırına takıldık. Lütfen 1 dakika bekle.")
            return
        if response.status_code != 200:
            await update.message.reply_text(f"❌ Veri alınamadı. API hatası: {response.status_code}")
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
                
            home_name = match.get("homeTeam", {}).get("name", "Bilinmeyen")
            away_name = match.get("awayTeam", {}).get("name", "Bilinmeyen")
            competition = match.get("competition", {}).get("name", "")
            utc_date = match.get("utcDate", "")[:16].replace("T", " ")
            home_id = match.get("homeTeam", {}).get("id")
            away_id = match.get("awayTeam", {}).get("id")
            comp_id = match.get("competition", {}).get("id")
            
            if status in ["LIVE", "IN_PLAY", "PAUSED"]: continue

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
            if total_exp_goals >= 2.8: gol_sinyal = "🔥 Üst 2.5 Güçlü"
            elif total_exp_goals <= 1.8: gol_sinyal = "🧊 Alt 2.5 Güçlü"

            if ms_sinyal or gol_sinyal:
                text = (
                    f"🏆 {competition}\n📅 {utc_date}\n"
                    f"🏠 {home_name} (Form: {home_form_str})\n🚪 {away_name} (Form: {away_form_str})\n"
                )
                if ms_sinyal: text += f"🎯 MS: {ms_sinyal} (Güven: {ms_guven})\n"
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
        await update.message.reply_text(f"⚠️ Futbol analizinde hata oluştu:\n{str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("basket", basket))
    
    print("Futbol & Basketbol Botu (Konferans Düzeltmeli) Başladı...")
    app.run_polling()

if __name__ == "__main__":
    main()
