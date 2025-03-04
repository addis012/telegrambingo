import os
import random
import asyncio
import logging
from flask import Flask, jsonify, request, session, render_template, redirect, url_for
from datetime import datetime
from database import db, init_db
from game_logic import BingoGame

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize database
init_db(app)

# Import models after db initialization
from models import User, Game, GameParticipant, Transaction

# Game storage (temporary, will be moved to database)
active_games = {}

@app.route('/')
def index():
    """Show available games or create a new one."""
    if 'user_id' not in session:
        session['user_id'] = random.randint(1, 1000000)  # Temporary user ID generation
    return render_template('game_lobby.html')

@app.route('/webhook/deposit', methods=['POST'])
def deposit_webhook():
    """Handle deposit webhook from Tasker"""
    try:
        # Get webhook data
        data = request.get_json()
        logger.info(f"Received deposit webhook: {data}")

        # Validate required fields
        if not data or 'amount' not in data or 'phone' not in data:
            error_msg = 'Invalid webhook data - must include amount and phone'
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 400

        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount format'}), 400

        # Process deposit through bot
        from bot import process_deposit_confirmation
        asyncio.run(process_deposit_confirmation(data))

        return jsonify({'status': 'success', 'message': 'Deposit processed successfully'})

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Error processing webhook: {error_msg}")
        return jsonify({'error': error_msg}), 500

@app.route('/webhook/test', methods=['POST'])
def test_webhook():
    """Test endpoint for webhook validation"""
    try:
        data = request.get_json()
        logger.info(f"Test webhook received: {data}")

        validation = {
            "format_check": [],
            "data_validation": [],
            "received_data": data
        }

        # Validate webhook format
        if not data:
            validation["format_check"].append("❌ No JSON data received")
            return jsonify(validation), 400

        # Check required fields
        required_fields = ['amount', 'phone']
        for field in required_fields:
            if field not in data:
                validation["format_check"].append(f"❌ Missing required field: {field}")
            else:
                validation["format_check"].append(f"✅ Found required field: {field}")

        # Validate amount
        try:
            amount = float(data.get('amount', 0))
            if amount <= 0:
                validation["data_validation"].append("❌ Amount must be positive")
            else:
                validation["data_validation"].append(f"✅ Valid amount: {amount}")
        except (ValueError, TypeError):
            validation["data_validation"].append("❌ Invalid amount format")

        # Validate phone
        phone = str(data.get('phone', ''))
        if not phone.isdigit() or len(phone) < 10:
            validation["data_validation"].append("❌ Invalid phone number format")
        else:
            validation["data_validation"].append(f"✅ Valid phone format: {phone}")

        # Overall validation status
        validation["status"] = "valid" if all(
            "❌" not in checks 
            for checks in validation["format_check"] + validation["data_validation"]
        ) else "invalid"

        return jsonify(validation)

    except Exception as e:
        logger.error(f"Error in webhook test: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "help": "Make sure to send a POST request with Content-Type: application/json"
        }), 500

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
        logger.exception(f"Error creating game: {str(e)}")
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)