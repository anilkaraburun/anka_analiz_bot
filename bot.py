import os
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Tokenlar
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

# API-Football Doğrudan Bağlantı Ayarları
API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}

# Yeni sisteme göre Lig ID'leri
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
    await update.message.reply_text(
        "Merhaba! Süper Lig destekli Gelişmiş Algoritma devrede. 🤖\n\n"
        "Komutlar:\n"
        "/maclar - İstatistiksel yapay zeka analizli maçlar\n"
        "/canli - Şu anki canlı maçlar"
    )

async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Süper Lig ve Avrupa maçları analiz ediliyor, lütfen bekle...")
    
    today = datetime.utcnow()
    # Sezonu otomatik belirle (Ağustos sonrası yeni sezon kabul edilir)
    season = today.year if today.month >= 7 else today.year - 1
    
    start_date = today.strftime("%Y-%m-%d")
    end_date = (today + timedelta(days=10)).strftime("%Y-%m-%d")
    
    standings_cache = {}
    mesajlar = []
    
    # 6 lig için döngü (Sıralama ve Fikstür verilerini çekme)
    for comp_id, comp_name in LEAGUES.items():
        # 1. Puan Durumu Çekimi
        std_url = f"{API_URL}/standings?league={comp_id}&season={season}"
        std_req = requests.get(std_url, headers=HEADERS)
        
        standings_cache[comp_id] = {}
        if std_req.status_code == 200 and std_req.json().get("response"):
            league_data = std_req.json()["response"][0]["league"]
            # Bazen ligler gruplara ayrılabilir, o yüzden ilk grubu alıyoruz
            for group in league_data.get("standings", []):
                for row in group:
                    team_id = row["team"]["id"]
                    standings_cache[comp_id][team_id] = row
                    
        # 2. Fikstür Çekimi (Gelecek 10 Gün)
        fix_url = f"{API_URL}/fixtures?league={comp_id}&season={season}&from={start_date}&to={end_date}"
        fix_req = requests.get(fix_url, headers=HEADERS)
        
        if fix_req.status_code != 200:
            continue
            
        fixtures = fix_req.json().get("response", [])
        
        for match in fixtures:
            status = match["fixture"]["status"]["short"]
            
            # Biten veya iptal olan maçları atla
            if status in ["FT", "AET", "PEN", "CANC", "PST", "ABD"]:
                continue
                
            home_team = match["teams"]["home"]["name"]
            away_team = match["teams"]["away"]["name"]
            utc_date = match["fixture"]["date"][:16].replace("T", " ")
            home_id = match["teams"]["home"]["id"]
            away_id = match["teams"]["away"]["id"]
            
            # Canlı Maç Kontrolü
            is_live = status in ["1H", "2H", "HT", "ET", "BT", "P", "LIVE"]
            if is_live:
                h_score = match["goals"]["home"] if match["goals"]["home"] is not None else 0
                a_score = match["goals"]["away"] if match["goals"]["away"] is not None else 0
                mesajlar.append(f"🔴 CANLI | {comp_name} | {home_team} {h_score}-{a_score} {away_team}")
                continue

            # Gelecek Maç Analizi (Sadece Başlamamış Maçlar)
            if status != "NS":
                continue
                
            home_stats = standings_cache[comp_id].get(home_id)
            away_stats = standings_cache[comp_id].get(away_id)
            
            if not (home_stats and away_stats):
                continue
                
            home_record = home_stats.get("home", {})
            away_record = away_stats.get("away", {})
            
            h_played = home_record.get("played", 0)
            a_played = away_record.get("played", 0)
            
            # SEZON BAŞI KURALI: En az 1 iç/dış saha maçı
            if h_played < 1 or a_played < 1:
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
            
            home_form_str = home_stats.get("form", "") or "Bilinmiyor"
            away_form_str = away_stats.get("form", "") or "Bilinmiyor"
            
            home_form_ppg = parse_form(home_form_str)
            away_form_ppg = parse_form(away_form_str)
            
            # GÜÇ ALGORİTMASI HESAPLAMASI
            home_power = (home_ppg * 0.4) + (home_form_ppg * 0.4) + ((home_gf - home_ga) * 0.2)
            away_power = (away_ppg * 0.4) + (away_form_ppg * 0.4) + ((away_gf - away_ga) * 0.2)
            
            power_diff = home_power - away_power
            
            # ALT / ÜST BEKLENTİSİ
            total_exp_goals = ((home_gf + away_ga) / 2) + ((away_gf + home_ga) / 2)
            
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
                
            if not ms_sinyal and not gol_sinyal:
                continue
                
            text = (
                f"🏆 {comp_name}\n"
                f"📅 {utc_date}\n"
                f"🏠 {home_team} (Son Form: {home_form_str})\n"
                f"🚪 {away_team} (Son Form: {away_form_str})\n"
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
    
    print("API-Football (Süper Lig) Gelişmiş Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
