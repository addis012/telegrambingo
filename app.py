import os
import random
from flask import Flask, jsonify, request, session, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from game_logic import BingoGame

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
    try:
        entry_price = int(request.json.get('entry_price', 10))
        if entry_price not in [10, 20, 50, 100]:
            return jsonify({'error': 'Invalid entry price'}), 400

        game_id = len(active_games) + 1
        active_games[game_id] = BingoGame(game_id, entry_price)

        # Add first player automatically
        user_id = session['user_id']
        game = active_games[game_id]
        game.add_player(user_id)

        return jsonify({
            'game_id': game_id,
            'entry_price': entry_price
        })
    except Exception as e:
        print(f"Error creating game: {str(e)}")  # Debug log
        return jsonify({'error': 'Failed to create game'}), 500

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
        return redirect(url_for('index'))

    game = active_games[game_id]
    user_id = session['user_id']

    # Add player if they haven't joined
    if user_id not in game.players:
        board = game.add_player(user_id)
        if not board:
            return redirect(url_for('index'))

    player = game.players[user_id]

    # Auto-start game if enough players have joined
    if game.status == "waiting" and len(game.players) >= 2:
        game.start_game()
        if game.status == "active":
            game.call_number()  # Call first number automatically

    # Get current call number
    current_number = None
    if game.status == "active" and game.called_numbers:
        current_number = game.format_number(game.called_numbers[-1])

    return render_template('game.html',
                         game_id=game_id,
                         board=player['board'],
                         marked=player['marked'],
                         called_numbers=game.called_numbers,
                         current_number=current_number,
                         active_players=len(game.players),
                         game_status=game.status,
                         entry_price=game.entry_price)

@app.route('/game/<int:game_id>/call', methods=['POST'])
def call_number(game_id):
    """Call the next number."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]

    # Auto-start game if enough players
    if game.status == "waiting" and len(game.players) >= 2:
        game.start_game()

    if game.status != "active":
        return jsonify({'error': 'Game not active'}), 400

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
    app.run(host='0.0.0.0', port=5000, debug=True)