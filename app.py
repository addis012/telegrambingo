import os
from flask import Flask, jsonify, request, session, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime
import random
from datetime import datetime

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

# Game storage (temporary, will be moved to database)
active_games = {}

# Models (retained from original)
class Game(db.Model):
    id = Column(Integer, primary_key=True)
    status = Column(String(20), default='waiting')  # waiting, active, finished
    entry_price = Column(Integer)
    pool = Column(Integer, default=0)
    called_numbers = Column(String, default='')
    created_at = Column(DateTime, default=datetime.utcnow)

class User(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class GameParticipant(db.Model):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    game_id = Column(Integer)
    cartela_number = Column(Integer)
    marked_numbers = Column(String, default='')
    created_at = Column(DateTime, default=datetime.utcnow)

def format_number(number: int) -> str:
    """Format a number into BINGO format (e.g., B-12)."""
    if 1 <= number <= 15:
        prefix = "B"
    elif 16 <= number <= 30:
        prefix = "I"
    elif 31 <= number <= 45:
        prefix = "N"
    elif 46 <= number <= 60:
        prefix = "G"
    else:
        prefix = "O"
    return f"{prefix}-{number}"

@app.route('/')
def index():
    """Show available games or create a new one."""
    if 'user_id' not in session:
        session['user_id'] = random.randint(1, 1000000)  # Temporary user ID generation

    return render_template('game_lobby.html')

@app.route('/game/create', methods=['POST'])
def create_game():
    """Create a new game."""
    entry_price = request.json.get('entry_price', 10)
    if entry_price not in [10, 20, 50, 100]:
        return jsonify({'error': 'Invalid entry price'}), 400

    game_id = len(active_games) + 1
    active_games[game_id] = BingoGame(game_id, entry_price)

    return jsonify({
        'game_id': game_id,
        'entry_price': entry_price
    })

@app.route('/game/<int:game_id>/join', methods=['POST'])
def join_game(game_id):
    """Join an existing game."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    user_id = session['user_id']

    board = game.add_player(user_id)
    if not board:
        return jsonify({'error': 'Could not join game'}), 400

    return jsonify({
        'board': board,
        'called_numbers': game.called_numbers
    })

@app.route('/game/<int:game_id>')
def play_game(game_id):
    """Show the game interface."""
    if game_id not in active_games:
        return "Game not found", 404

    game = active_games[game_id]
    user_id = session['user_id']

    if user_id not in game.players:
        game.add_player(user_id)

    player = game.players[user_id]
    return render_template('game.html',
                         game_id=game_id,
                         board=player['board'],
                         marked=player['marked'],
                         called_numbers=game.called_numbers,
                         current_number=game.call_number() if game.status == "active" else "")

@app.route('/game/<int:game_id>/call', methods=['POST'])
def call_number(game_id):
    """Call the next number."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    number = game.call_number()

    return jsonify({
        'number': number,
        'called_numbers': game.called_numbers
    })

@app.route('/game/<int:game_id>/mark', methods=['POST'])
def mark_number(game_id):
    """Mark a number on the player's board."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    user_id = session['user_id']
    number = request.json.get('number')

    if not number:
        return jsonify({'error': 'Number required'}), 400

    success = game.mark_number(user_id, number)
    if not success:
        return jsonify({'error': 'Invalid number'}), 400

    winner, message = game.check_winner(user_id)
    if winner:
        game.end_game(user_id)

    return jsonify({
        'marked': game.players[user_id]['marked'],
        'winner': winner,
        'message': message
    })

@app.route('/game/<int:game_id>/start', methods=['POST'])
def start_game(game_id):
    """Start the game."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    if game.start_game():
        return jsonify({'status': 'Game started'})
    return jsonify({'error': 'Could not start game'}), 400

@app.route('/game/list')
def list_games():
    """List all available games."""
    games = []
    for game_id, game in active_games.items():
        if game.status == "waiting":
            games.append({
                'id': game_id,
                'players': len(game.players),
                'entry_price': game.entry_price
            })
    return jsonify(games)

if __name__ == '__main__':
    from game_logic import BingoGame
    app.run(host='0.0.0.0', port=5000, debug=True)