import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
FOOTBALL_TOKEN = os.getenv("FOOTBALL_TOKEN")

API_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": FOOTBALL_TOKEN
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hata Tespit Modu aktif. Lütfen /test yazın.")

async def test_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("API sunucularına bağlanılıyor, lütfen bekle...")
    
    status_url = f"{API_URL}/status"
    res = requests.get(status_url, headers=HEADERS)
    
    if res.status_code != 200:
        await update.message.reply_text(f"❌ HATA! API'ye bağlanılamadı.\nDurum Kodu: {res.status_code}\nDetay: {res.text}")
        return
        
    data = res.json()
    if data.get("errors"):
        await update.message.reply_text(f"⚠️ API SUNUCUSU HATA VERDİ:\n{data['errors']}")
        return
        
    account_info = data.get("response", {}).get("account", {})
    subscription = data.get("response", {}).get("subscription", {})
    
    mesaj = (
        "✅ API BAĞLANTISI KUSURSUZ!\n"
        f"Ad: {account_info.get('firstname', 'Bilinmiyor')}\n"
        f"Plan: {subscription.get('plan', 'Bilinmiyor')}\n"
        f"Kullanılan İstek: {subscription.get('requests', {}).get('current', 0)} / {subscription.get('requests', {}).get('limit_day', 0)}\n\n"
        "Sorun hesapta değil! Muhtemelen liglerin sezon yılı güncellenmemiş. Lütfen bu mesajı bana kopyala."
    )
    await update.message.reply_text(mesaj)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test_api))
    
    print("Test Bot Başladı...")
    app.run_polling()

if __name__ == "__main__":
    main()
