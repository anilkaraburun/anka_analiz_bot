import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

# ====================== AYARLAR ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")
APISPORTS_TOKEN = os.getenv("APISPORTS_TOKEN")

headers_football = {"X-Auth-Token": FOOTBALL_TOKEN}
headers_apisports = {"x-apisports-key": APISPORTS_TOKEN}

ISTENEN_FUTBOL_LIGLERI = [
    "Premier League", "Primera Division", "Serie A",
    "Bundesliga", "Ligue 1", "UEFA Champions League"
]

ISTENEN_BASKET_LIGLERI = ["NBA", "WNBA", "Euroleague", "Super Lig", "BSL", "Liga ACB"]
ISTENEN_VOLEYBOL_LIGLERI = ["SuperLega", "PlusLiga", "Efeler Ligi", "Sultanlar Ligi", "Champions League"]
ISTENEN_HOKEY_LIGLERI = ["NHL", "KHL", "SHL", "Liiga"]
ISTENEN_HENTBOL_LIGLERI = ["Champions League", "Bundesliga", "LNH Division 1"]

TZ = ZoneInfo("Europe/Istanbul")


# ====================== YARDIMCI FONKSİYONLAR ======================
def parse_form(form_str: str) -> float:
    """WWDL formunu 0-3 arası puana çevirir"""
    if not form_str:
        return 1.5
    form_str = str(form_str).replace(",", "").replace(" ", "").upper()
    if not form_str:
        return 1.5
    pts = sum(3 if c == "W" else 1 if c == "D" else 0 for c in form_str)
    return pts / len(form_str)


def normalize_averaj(value: float, scale: float = 4.0) -> float:
    """Averajı makul aralığa sıkıştırır (-1.5 ~ +1.5)"""
    return max(min(value / scale, 1.5), -1.5)


def calculate_power(win_rate: float, form_val: float, averaj: float) -> float:
    """
    Normalize edilmiş güç hesabı
    %45 Galibiyet + %35 Form + %20 Averaj
    """
    form_norm = form_val / 3.0          # 0-1 arası
    averaj_norm = normalize_averaj(averaj)
    return (win_rate * 0.45) + (form_norm * 0.35) + (averaj_norm * 0.20)


def safe_get(data: dict, *keys, default=0):
    """İç içe dict'ten güvenli değer alma"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data not in (None, {}) else default


# ====================== MENÜ ======================
async def setup_menu(application: Application):
    commands = [
        BotCommand("start", "🤖 Botu başlatır"),
        BotCommand("maclar", "⚽ Futbol Analizi"),
        BotCommand("basket", "🏀 Basketbol Analizi"),
        BotCommand("voleybol", "🏐 Voleybol Analizi"),
        BotCommand("hokey", "🏒 Buz Hokeyi Analizi"),
        BotCommand("hentbol", "🤾 Hentbol Analizi"),
    ]
    await application.bot.set_my_commands(commands)
    print("Menü yüklendi.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏆 **Multi-Spor Analiz Botu**\n\n"
        "Menüden spor seçerek form + galibiyet + averaj bazlı analiz alabilirsin.\n\n"
        "⚠️ Bu bot sadece istatistiksel sinyal üretir. Bahis tavsiyesi değildir."
    )


# ====================== API-SPORTS ORTAK MOTOR ======================
async def apisports_analyzer(update: Update, sport_name: str, base_url: str, leagues: list, icon: str):
    if not APISPORTS_TOKEN:
        await update.message.reply_text("⚠️ APISPORTS_TOKEN bulunamadı.")
        return

    await update.message.reply_text(f"{icon} {sport_name} maçları analiz ediliyor...")

    try:
        today = datetime.now(TZ).date()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]

        all_games = []
        for d in dates:
            res = requests.get(
                f"{base_url}/games?date={d}",
                headers=headers_apisports,
                timeout=12
            )
            if res.status_code == 200:
                all_games.extend(res.json().get("response", []))

        filtered = [
            g for g in all_games
            if any(l.lower() in g.get("league", {}).get("name", "").lower() for l in leagues)
        ]

        if not filtered:
            await update.message.reply_text(f"ℹ️ Bugün/yarın seçili {sport_name} liglerinde maç yok.")
            return

        # Standings cache
        leagues_set = {(g["league"]["id"], g["league"].get("season")) for g in filtered}
        standings_cache = {}

        for lig_id, season in leagues_set:
            if not season:
                continue
            std_res = requests.get(
                f"{base_url}/standings?league={lig_id}&season={season}",
                headers=headers_apisports,
                timeout=12
            )
            if std_res.status_code != 200:
                continue

            team_dict = {}
            for item in std_res.json().get("response", []):
                rows = item if isinstance(item, list) else [item]
                for row in rows:
                    t_id = row.get("team", {}).get("id")
                    if t_id:
                        team_dict[t_id] = row
            standings_cache[lig_id] = team_dict

        mesajlar = []

        for game in filtered:
            status = game.get("status", {}).get("short", "")
            if status in ["FT", "AOT", "CANC", "POST", "LIVE", "IN_PLAY", "HT"]:
                continue

            lig_id = game["league"]["id"]
            lig_adi = game["league"]["name"]
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_id, away_id = home["id"], away["id"]
            saat = game["date"][:16].replace("T", " ")

            stats = standings_cache.get(lig_id, {})
            h_stats = stats.get(home_id, {})
            a_stats = stats.get(away_id, {})

            h_games = h_stats.get("games", {})
            a_games = a_stats.get("games", {})

            h_played = safe_get(h_games, "played") or safe_get(h_games, "played", "all") or 0
            a_played = safe_get(a_games, "played") or safe_get(a_games, "played", "all") or 0

            if h_played < 3 or a_played < 3:
                continue

            h_win = safe_get(h_games, "win", "total") or safe_get(h_games, "won", "total") or 0
            a_win = safe_get(a_games, "win", "total") or safe_get(a_games, "won", "total") or 0

            home_win_rate = h_win / h_played
            away_win_rate = a_win / a_played

            # Gol / Sayı / Set
            h_pts = h_stats.get("goals") or h_stats.get("points") or {}
            a_pts = a_stats.get("goals") or a_stats.get("points") or {}

            home_for = (safe_get(h_pts, "for") or 0) / h_played
            home_against = (safe_get(h_pts, "against") or 0) / h_played
            away_for = (safe_get(a_pts, "for") or 0) / a_played
            away_against = (safe_get(a_pts, "against") or 0) / a_played

            h_averaj = home_for - home_against
            a_averaj = away_for - away_against

            home_form = parse_form(h_stats.get("form"))
            away_form = parse_form(a_stats.get("form"))

            home_power = calculate_power(home_win_rate, home_form, h_averaj)
            away_power = calculate_power(away_win_rate, away_form, a_averaj)
            power_diff = home_power - away_power

            exp_total = (home_for + away_against) / 2 + (away_for + home_against) / 2

            # Sinyal
            ms_sinyal = ""
            if power_diff >= 0.45:
                ms_sinyal = "1️⃣ Net Ev Sahibi (Yüksek)"
            elif power_diff >= 0.22:
                ms_sinyal = "1️⃣ Ev Sahibi Avantajlı (Orta)"
            elif power_diff <= -0.45:
                ms_sinyal = "2️⃣ Net Deplasman (Yüksek)"
            elif power_diff <= -0.22:
                ms_sinyal = "2️⃣ Deplasman Avantajlı (Orta)"

            if not ms_sinyal:
                continue

            text = (
                f"🏆 {lig_adi}\n"
                f"📅 {saat}\n"
                f"🏠 {home['name']}  (Form: {str(h_stats.get('form', '?')).replace(',','')})\n"
                f"🚪 {away['name']}  (Form: {str(a_stats.get('form', '?')).replace(',','')})\n"
                f"🎯 MS: {ms_sinyal}\n"
                f"📊 Güç Farkı: {power_diff:+.2f}\n"
                f"⚙️ Beklenen Toplam: {exp_total:.1f}"
            )
            mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text(f"Şu an analiz edilebilir {sport_name} maçı yok.")
            return

        full = "\n────────────────────\n".join(mesajlar)
        for i in range(0, len(full), 4000):
            await update.message.reply_text(full[i:i+4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ {sport_name} analizinde hata:\n{str(e)}")


# ====================== KOMUTLAR ======================
async def basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Basketbol", "https://v1.basketball.api-sports.io", ISTENEN_BASKET_LIGLERI, "🏀")


async def voleybol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Voleybol", "https://v1.volleyball.api-sports.io", ISTENEN_VOLEYBOL_LIGLERI, "🏐")


async def hokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Buz Hokeyi", "https://v1.hockey.api-sports.io", ISTENEN_HOKEY_LIGLERI, "🏒")


async def hentbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await apisports_analyzer(update, "Hentbol", "https://v1.handball.api-sports.io", ISTENEN_HENTBOL_LIGLERI, "🤾")


# ====================== FUTBOL ======================
async def maclar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Futbol maçları analiz ediliyor...")

    try:
        today = datetime.now(TZ).date()
        end = today + timedelta(days=5)
        url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={end}"

        res = requests.get(url, headers=headers_football, timeout=12)
        if res.status_code != 200:
            await update.message.reply_text(f"❌ Futbol API hatası: {res.status_code}")
            return

        matches = res.json().get("matches", [])
        filtered = [
            m for m in matches
            if any(l.lower() in m.get("competition", {}).get("name", "").lower() for l in ISTENEN_FUTBOL_LIGLERI)
        ]

        if not filtered:
            await update.message.reply_text("Önümüzdeki günlerde belirtilen liglerde maç bulunamadı.")
            return

        # Standings
        competitions = {m["competition"]["id"] for m in filtered}
        standings_cache = {}

        for comp_id in competitions:
            r = requests.get(
                f"https://api.football-data.org/v4/competitions/{comp_id}/standings",
                headers=headers_football,
                timeout=12
            )
            if r.status_code != 200:
                continue
            tables = r.json().get("standings", [])
            standings_cache[comp_id] = {
                "total": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "TOTAL"), [])},
                "home": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "HOME"), [])},
                "away": {row["team"]["id"]: row for row in next((t["table"] for t in tables if t["type"] == "AWAY"), [])},
            }

        mesajlar = []

        for match in filtered:
            if match.get("status") in ["FINISHED", "LIVE", "IN_PLAY", "PAUSED"]:
                continue

            home_id = match["homeTeam"]["id"]
            away_id = match["awayTeam"]["id"]
            comp_id = match["competition"]["id"]
            data = standings_cache.get(comp_id)
            if not data:
                continue

            total_h = data["total"].get(home_id) or {}
            total_a = data["total"].get(away_id) or {}
            if not total_h or not total_a:
                continue

            h_stats = data["home"].get(home_id) or total_h
            a_stats = data["away"].get(away_id) or total_a

            h_played = h_stats.get("playedGames", 0)
            a_played = a_stats.get("playedGames", 0)
            if h_played < 3 or a_played < 3:
                continue

            home_ppg = h_stats.get("points", 0) / h_played
            away_ppg = a_stats.get("points", 0) / a_played

            home_gf = h_stats.get("goalsFor", 0) / h_played
            home_ga = h_stats.get("goalsAgainst", 0) / h_played
            away_gf = a_stats.get("goalsFor", 0) / a_played
            away_ga = a_stats.get("goalsAgainst", 0) / a_played

            home_form = parse_form(total_h.get("form"))
            away_form = parse_form(total_a.get("form"))

            # Futbol için özel güç (ppg bazlı)
            home_power = (home_ppg / 3 * 0.45) + (home_form / 3 * 0.35) + (normalize_averaj(home_gf - home_ga) * 0.20)
            away_power = (away_ppg / 3 * 0.45) + (away_form / 3 * 0.35) + (normalize_averaj(away_gf - away_ga) * 0.20)
            power_diff = home_power - away_power

            exp_goals = (home_gf + away_ga) / 2 + (away_gf + home_ga) / 2

            ms_sinyal = ""
            if power_diff >= 0.28:
                ms_sinyal = "1️⃣ Net Ev Sahibi"
            elif power_diff >= 0.14:
                ms_sinyal = "1️⃣ veya 1X"
            elif power_diff <= -0.28:
                ms_sinyal = "2️⃣ Net Deplasman"
            elif power_diff <= -0.14:
                ms_sinyal = "2️⃣ veya X2"

            gol_sinyal = ""
            if exp_goals >= 2.65:
                gol_sinyal = "🔥 Üst 2.5"
            elif exp_goals <= 2.05:
                gol_sinyal = "🧊 Alt 2.5"

            if not (ms_sinyal or gol_sinyal):
                continue

            text = (
                f"🏆 {match['competition']['name']}\n"
                f"📅 {match['utcDate'][:16].replace('T', ' ')}\n"
                f"🏠 {match['homeTeam']['name']}  (Form: {str(total_h.get('form', '?')).replace(',','')})\n"
                f"🚪 {match['awayTeam']['name']}  (Form: {str(total_a.get('form', '?')).replace(',','')})\n"
            )
            if ms_sinyal:
                text += f"🎯 MS: {ms_sinyal}\n"
            if gol_sinyal:
                text += f"⚽ Gol: {gol_sinyal} (Beklenen: {exp_goals:.1f})\n"
            text += f"📊 Güç Farkı: {power_diff:+.2f}"

            mesajlar.append(text)

        if not mesajlar:
            await update.message.reply_text("Şu an analiz edilebilir futbol maçı yok.")
            return

        full = "\n────────────────────\n".join(mesajlar)
        for i in range(0, len(full), 4000):
            await update.message.reply_text(full[i:i+4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ Futbol analizinde hata:\n{str(e)}")


# ====================== MAIN ======================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(setup_menu).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("maclar", maclar))
    app.add_handler(CommandHandler("basket", basket))
    app.add_handler(CommandHandler("voleybol", voleybol))
    app.add_handler(CommandHandler("hokey", hokey))
    app.add_handler(CommandHandler("hentbol", hentbol))

    print("Multi-Spor Botu çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
