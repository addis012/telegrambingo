from app import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False)
    username = db.Column(db.String(64))
    phone = db.Column(db.String(20))
    balance = db.Column(db.Float, default=0.0)
    games_played = db.Column(db.Integer, default=0)
    games_won = db.Column(db.Integer, default=0)
    referrer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    games_participated = db.relationship('GameParticipant', backref='user', lazy=True)
    won_games = db.relationship('Game', backref='winner', lazy=True)

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default='waiting')  # waiting, active, finished
    entry_price = db.Column(db.Float, nullable=False)
    pool = db.Column(db.Float, default=0.0)
    winner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)

    # Relationships
    participants = db.relationship('GameParticipant', backref='game', lazy=True)

class GameParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cartela_number = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('game_id', 'cartela_number', name='unique_cartela_per_game'),
    )