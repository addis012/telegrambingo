import os
import random
from flask import Flask, render_template, jsonify, session

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

class BingoGame:
    def __init__(self):
        self.current_number = None
        self.called_numbers = []
        self.status = "waiting"

    def call_number(self):
        available = [n for n in range(1, 76) if n not in self.called_numbers]
        if not available:
            return None
        number = random.choice(available)
        self.current_number = number
        self.called_numbers.append(number)
        return self.format_number(number)

    @staticmethod
    def format_number(number):
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

game = BingoGame()

@app.route('/')
def index():
    if 'board' not in session:
        # Generate a random board for the player
        numbers = random.sample(range(1, 76), 25)
        session['board'] = numbers
        session['marked'] = []

    return render_template('game.html', 
                         board=session['board'],
                         marked=session['marked'],
                         current_number=game.current_number)

@app.route('/call')
def call_number():
    number = game.call_number()
    return jsonify({'number': number})

@app.route('/mark/<int:number>')
def mark_number(number):
    if 'marked' not in session:
        session['marked'] = []
    marked = session['marked']
    if number not in marked:
        marked.append(number)
        session['marked'] = marked
    return jsonify({'marked': marked})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)