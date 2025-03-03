import asyncio
import threading
from admin_panel import app
from bot import bot, dp

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=True)

async def main():
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start the Telegram bot
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())