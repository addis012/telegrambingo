import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure the SQLAlchemy part of the app
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize SQLAlchemy with the app
db.init_app(app)

def init_db():
    with app.app_context():
        # Import models here to avoid circular imports
        from models import User, Game, GameParticipant

        # Drop all tables first to ensure clean state
        db.drop_all()
        # Create all tables
        db.create_all()

        print("Database tables created successfully!")

# Initialize database tables
init_db()

# Import routes after db initialization to avoid circular imports
from admin_panel import *  # This will register the admin routes