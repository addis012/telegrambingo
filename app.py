import os
import random
import asyncio
from flask import Flask, jsonify, request, session, render_template, redirect, url_for
from datetime import datetime
from database import db, init_db
from game_logic import BingoGame

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database
init_db(app)

# Import models after db initialization
from models import User, Game, GameParticipant, Transaction

# Game storage (temporary, will be moved to database)
active_games = {}

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

@app.route('/game/create', methods=['GET', 'POST'])
def create_game():
    """Create a new game."""
    try:
        if request.method == 'POST':
            entry_price = int(request.json.get('entry_price', 10))
            user_id = request.json.get('user_id')

            if entry_price not in [10, 20, 50, 100]:
                return jsonify({'error': 'Invalid entry price'}), 400

            game_id = len(active_games) + 1
            active_games[game_id] = BingoGame(game_id, entry_price)

            # Store user_id in session for web app
            session['user_id'] = user_id

            return jsonify({
                'game_id': game_id,
                'entry_price': entry_price
            })
        else:
            return jsonify({'error': 'Invalid request method'}), 405
    except Exception as e:
        print(f"Error creating game: {str(e)}")  # Debug log
        return jsonify({'error': 'Failed to create game'}), 500

@app.route('/game/<int:game_id>/select_cartela')
def select_cartela(game_id):
    """Show cartela selection interface"""
    if game_id not in active_games:
        return redirect(url_for('index'))

    game = active_games[game_id]

    # Get list of used cartela numbers
    used_cartelas = set()
    for player in game.players.values():
        used_cartelas.add(player.get('cartela_number', 0))

    return render_template(
        'cartela_selection.html',
        game_id=game_id,
        entry_price=game.entry_price,
        used_cartelas=used_cartelas
    )

@app.route('/game/<int:game_id>/join', methods=['POST'])
def join_game(game_id):
    """Join a game with selected cartela number"""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    user_id = session['user_id']
    cartela_number = request.json.get('cartela_number')

    if not cartela_number or cartela_number < 1 or cartela_number > 100:
        return jsonify({'error': 'Invalid cartela number'}), 400

    # Check if cartela is already taken
    for player in game.players.values():
        if player.get('cartela_number') == cartela_number:
            return jsonify({'error': 'This cartela is already taken'}), 400

    # Add player with specific cartela
    board = game.add_player(user_id, cartela_number)
    if not board:
        return jsonify({'error': 'Could not join game'}), 400

    return jsonify({
        'game_id': game_id,
        'board': board,
        'cartela_number': cartela_number
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
    if game.status == "waiting" and len(game.players) >= game.min_players:
        game.start_game()
        if game.status == "active":
            game.call_number()  # Call first number automatically

    # Get current call number
    current_number = None
    if game.status == "active" and game.called_numbers:
        current_number = game.format_number(game.called_numbers[-1])

    return render_template('game.html',
                         game_id=game_id,
                         game=game,
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
    if game.status == "waiting" and len(game.players) >= game.min_players:
        game.start_game()

    if game.status != "active":
        return jsonify({'error': 'Game not active'}), 400

    number = game.call_number()
    if number:
        return jsonify({
            'number': number,
            'called_numbers': game.called_numbers
        })
    return jsonify({'error': 'No more numbers to call'}), 400

@app.route('/game/<int:game_id>/mark', methods=['POST'])
def mark_number(game_id):
    """Mark a number on the player's board."""
    if game_id not in active_games:
        return jsonify({'error': 'Game not found'}), 404

    game = active_games[game_id]
    user_id = session['user_id']

    if user_id not in game.players:
        return jsonify({'error': 'Player not in game'}), 400

    # Handle bingo check request
    check_win = request.json.get('check_win', False)
    if check_win:
        winner, message = game.check_winner(user_id)
        if winner:
            game.end_game(user_id)
        return jsonify({
            'winner': winner,
            'message': message
        })

    # Handle number marking
    number = request.json.get('number')
    if not number:
        return jsonify({'error': 'Number required'}), 400

    # Validate the number is on player's board and has been called
    player = game.players[user_id]
    if number not in player['board']:
        return jsonify({'error': 'Number not on your board'}), 400
    if number not in game.called_numbers:
        return jsonify({'error': 'Number has not been called yet'}), 400

    success = game.mark_number(user_id, number)
    if not success:
        return jsonify({'error': 'Could not mark number'}), 400

    # Check for win after marking
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

# Add deposit confirmation endpoint
@app.route('/deposit/confirm', methods=['POST'])
def confirm_deposit():
    """Handle deposit confirmation from Tasker"""
    try:
        data = request.get_json()
        if not data or 'amount' not in data or 'phone' not in data:
            error_msg = 'Invalid data format - must include amount and phone'
            print(error_msg)
            return jsonify({'error': error_msg}), 400

        print(f"Received deposit confirmation: {data}")

        # Forward the confirmation to the bot
        from bot import process_deposit_confirmation
        asyncio.run(process_deposit_confirmation(data))

        return jsonify({'status': 'success'})
    except ValueError as e:
        # Handle validation errors
        error_msg = str(e)
        print(f"Validation error: {error_msg}")
        return jsonify({'error': error_msg}), 400
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing deposit confirmation: {error_msg}")
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)