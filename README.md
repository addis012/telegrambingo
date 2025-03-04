# Bingo Game Bot

A Telegram-based Bingo game bot that enables multiplayer Bingo gameplay through an interactive mini-app interface.

## Features

- Supports multiplayer Bingo with flexible player count
- Real-time number calling with consistent board generation
- Dynamic board marking with free center space
- Responsive web-based game interface integrated with Telegram
- PostgreSQL database for robust game state management
- Webhook support for external automation systems
- Telegram bot backend providing seamless game coordination

## Tech Stack

- Python 3.11
- Flask (Web Framework)
- aiogram (Telegram Bot Framework)
- PostgreSQL (Database)
- SQLAlchemy (ORM)
- Bootstrap (Frontend)

## Setup Instructions

1. Clone the repository
```bash
git clone https://github.com/yourusername/bingo-game-bot.git
cd bingo-game-bot
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql://user:password@host:port/dbname
SESSION_SECRET=your_secret_key
```

4. Initialize the database
```bash
flask db upgrade
```

5. Run the application
```bash
python main.py
```

## Project Structure

```
├── app.py              # Flask application
├── bot.py              # Telegram bot implementation
├── database.py         # Database configuration
├── game_logic.py       # Bingo game logic
├── models.py           # Database models
├── static/            # Static files (CSS, JS)
└── templates/         # HTML templates
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
