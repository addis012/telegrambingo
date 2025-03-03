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

# Create the app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize SQLAlchemy
db.init_app(app)

# Models
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
    """Test route for game interface."""
    if 'user_id' not in session:
        session['user_id'] = 1  # Test user ID

    # Generate a test board
    b_numbers = random.sample(range(1, 16), 5)
    i_numbers = random.sample(range(16, 31), 5)
    n_numbers = random.sample(range(31, 46), 5)
    g_numbers = random.sample(range(46, 61), 5)
    o_numbers = random.sample(range(61, 76), 5)

    board = []
    for i in range(5):
        board.extend([b_numbers[i], i_numbers[i], n_numbers[i], g_numbers[i], o_numbers[i]])

    return render_template('game.html',
                         board=board,
                         marked=[],
                         called_numbers=[],
                         current_number="B-11")

@app.route('/test_db')
def test_db():
    """Test database connection and operations."""
    try:
        # Create a test game
        game = Game(entry_price=10, status='waiting')
        db.session.add(game)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Database connection working',
            'game_id': game.id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/call', methods=['POST'])
def call_number():
    """Call a random number."""
    number = random.randint(1, 75)
    formatted = format_number(number)
    return jsonify({'number': formatted})

@app.route('/mark/<int:number>', methods=['POST'])
def mark_number(number):
    """Mark a number on player's board."""
    if 'marked' not in session:
        session['marked'] = []
    marked = session.get('marked', [])
    if number not in marked:
        marked.append(number)
        session['marked'] = marked
    return jsonify({'marked': marked})

@app.route('/game/create', methods=['POST'])
def create_game():
    entry_price = request.json.get('entry_price', 10)  # Default price 10 birr
    if entry_price not in [10, 20, 50, 100]:
        return jsonify({'error': 'Invalid entry price'}), 400

    game = Game(
        status='waiting',
        entry_price=entry_price,
        pool=0,
        called_numbers=''
    )
    db.session.add(game)
    db.session.commit()

    return jsonify({
        'game_id': game.id,
        'status': game.status,
        'entry_price': game.entry_price
    })

@app.route('/game/<int:game_id>/join', methods=['POST'])
def join_game():
    game_id = request.json.get('game_id')
    user_id = session.get('user_id')
    cartela_number = request.json.get('cartela_number')

    if not all([game_id, user_id, cartela_number]):
        return jsonify({'error': 'Missing required parameters'}), 400

    game = Game.query.get_or_404(game_id)
    if game.status != 'waiting':
        return jsonify({'error': 'Game already started'}), 400

    # Check if cartela is already taken
    existing = GameParticipant.query.filter_by(
        game_id=game_id,
        cartela_number=cartela_number
    ).first()
    if existing:
        return jsonify({'error': 'Cartela number already taken'}), 400

    # Create game participant
    participant = GameParticipant(
        game_id=game_id,
        user_id=user_id,
        cartela_number=cartela_number,
        marked_numbers=''
    )
    db.session.add(participant)

    # Update game pool
    game.pool += game.entry_price
    db.session.commit()

    return jsonify({
        'message': 'Successfully joined game',
        'cartela_number': cartela_number
    })

@app.route('/game/<int:game_id>/call', methods=['POST'])
def call_number_route(game_id):
    game = Game.query.get_or_404(game_id)
    if game.status != 'active':
        return jsonify({'error': 'Game not active'}), 400

    # Get previously called numbers
    called = [int(n) for n in game.called_numbers.split(',') if n] if game.called_numbers else []

    # Get available numbers
    available = [n for n in range(1, 76) if n not in called]
    if not available:
        return jsonify({'error': 'No more numbers available'}), 400

    # Call new number
    number = random.choice(available)
    called.append(number)
    game.called_numbers = ','.join(map(str, called))
    db.session.commit()

    # Format number (B-1, I-16, etc)
    formatted = format_number(number)

    return jsonify({
        'number': number,
        'formatted': formatted,
        'called_numbers': called
    })

@app.route('/game/<int:game_id>/mark', methods=['POST'])
def mark_number_route(game_id):
    user_id = session.get('user_id')
    number = request.json.get('number')

    if not number:
        return jsonify({'error': 'Number required'}), 400

    participant = GameParticipant.query.filter_by(
        game_id=game_id,
        user_id=user_id
    ).first_or_404()

    # Get marked numbers
    marked = [int(n) for n in participant.marked_numbers.split(',') if n] if participant.marked_numbers else []

    # Mark new number if not already marked
    if number not in marked:
        marked.append(number)
        participant.marked_numbers = ','.join(map(str, marked))
        db.session.commit()

    return jsonify({
        'marked_numbers': marked
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)