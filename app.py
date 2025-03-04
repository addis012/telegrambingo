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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)