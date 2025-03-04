import os
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from flask import Flask
from database import db, init_db
from models import User, Transaction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Configuration
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

WEBAPP_URL = f"https://{os.getenv('REPLIT_SLUG')}.replit.app" if os.getenv('REPLIT_SLUG') else "http://0.0.0.0:5000"
router = Router()

# Initialize Flask app for database context
app = Flask(__name__)
init_db(app)

# Game prices
GAME_PRICES = [10, 20, 50, 100]

# States
class UserState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_deposit_sms = State()
    waiting_for_withdrawal = State()

async def setup_bot():
    """Setup bot and dispatcher"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    bot = Bot(token=TOKEN)

    # Include router
    dp.include_router(router)

    logger.info("Bot setup completed")
    return bot, dp

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command and registration"""
    with app.app_context():
        user_id = message.from_user.id

        # Check for referral
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        referrer_id = int(args[0]) if args else None

        # Check if user exists
        user = User.query.filter_by(telegram_id=user_id).first()

        if not user:
            # New user registration
            try:
                user = User(
                    telegram_id=user_id,
                    username=message.from_user.username,
                    referrer_id=referrer_id
                )
                db.session.add(user)
                db.session.commit()

                keyboard = ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="📱 Share Phone Number", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )

                await message.answer(
                    "Welcome to Addis Bingo! 🎮\n\n"
                    "Please share your phone number to complete registration.",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                await message.answer("Sorry, there was an error. Please try again later.")
        else:
            # Returning user - show main menu
            await show_main_menu(message)

async def show_main_menu(message: Message):
    """Show main menu with balance and options"""
    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🎮 Play Bingo")],
                [KeyboardButton(text="💰 Deposit"), KeyboardButton(text="💳 Withdraw")],
                [KeyboardButton(text="📊 My Stats")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            f"🎯 Main Menu\n\n"
            f"💰 Balance: {user.balance:.2f} birr\n"
            f"🎮 Games played: {user.games_played}\n"
            f"🏆 Games won: {user.games_won}\n",
            reply_markup=keyboard
        )

@router.message(F.contact)
async def process_phone_number(message: Message):
    """Handle shared contact information"""
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer("Please share your own contact information.")
        return

    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("Please use /start first!")
            return

        user.phone = message.contact.phone_number
        db.session.commit()

        # Generate referral link
        bot = Bot(token=TOKEN)
        bot_info = await bot.get_me()
        referral_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

        await message.answer(
            "✅ Registration complete!\n\n"
            f"Your referral link: {referral_link}\n\n"
            "Share this link with friends and earn 20 birr when they:\n"
            "1. Register and verify their phone number\n"
            "2. Make their first deposit\n"
            "3. Play their first game\n",
            reply_markup=ReplyKeyboardRemove()
        )

        # Show main menu
        await show_main_menu(message)

@router.message(F.text == "🎮 Play Bingo")
async def process_play_command(message: Message):
    """Handle play command - show game price options"""
    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()

        if not user:
            await message.answer("Please register first using /start")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{price} Birr",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/game/new?price={price}")
            )] for price in GAME_PRICES
        ])

        await message.answer(
            "Choose your game entry price:",
            reply_markup=keyboard
        )

@router.message(F.text == "💰 Deposit")
async def process_deposit_command(message: Message, state: FSMContext):
    """Handle deposit command"""
    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("Please register first using /start")
            return

        # Create pending transaction
        transaction = Transaction(
            user_id=user.id,
            type='deposit',
            amount=0,  # Will be updated when SMS is received
            status='pending'
        )
        db.session.add(transaction)
        db.session.commit()

        await state.set_state(UserState.waiting_for_deposit_sms)
        await message.answer(
            "To deposit funds:\n\n"
            "1. Send money to one of these accounts:\n"
            "   - CBE: 1000123456 (Abebe)\n"
            "   - Telebirr: 0911111111\n"
            "2. Forward the confirmation SMS to this bot\n\n"
            "⚠️ Important: Only forward SMS from official bank numbers!"
        )

@router.message(F.text == "💳 Withdraw")
async def process_withdraw_command(message: Message, state: FSMContext):
    """Handle withdraw command"""
    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("Please register first using /start")
            return

        if user.balance < 100:
            await message.answer("⚠️ Minimum withdrawal amount is 100 birr")
            return

        await state.set_state(UserState.waiting_for_withdrawal)
        await message.answer(
            "💳 Withdrawal Rules:\n\n"
            "1. Minimum: 100 birr\n"
            "2. Must have played at least 5 games\n"
            "3. Processing time: 24 hours\n\n"
            "Reply with the amount you want to withdraw:"
        )

@router.message(F.text == "📊 My Stats")
async def process_stats_command(message: Message):
    """Handle stats command"""
    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("Please register first using /start")
            return

        # Get transaction history
        transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.created_at.desc()).limit(5).all()

        stats = (
            f"📊 Your Stats\n\n"
            f"💰 Current Balance: {user.balance:.2f} birr\n"
            f"🎮 Games Played: {user.games_played}\n"
            f"🏆 Games Won: {user.games_won}\n\n"
            f"Recent Transactions:\n"
        )

        for tx in transactions:
            stats += f"{'➕' if tx.amount > 0 else '➖'} {abs(tx.amount)} birr - {tx.type} ({tx.status})\n"

        await message.answer(stats)

@router.message(UserState.waiting_for_deposit_sms)
async def process_deposit_sms(message: Message, state: FSMContext):
    """Handle deposit SMS verification"""
    if not message.forward_date:
        await message.answer("⚠️ Please forward the SMS, don't type it manually!")
        return

    with app.app_context():
        user = User.query.filter_by(telegram_id=message.from_user.id).first()

        transaction = Transaction.query.filter_by(
            user_id=user.id,
            type='deposit',
            status='pending'
        ).order_by(Transaction.created_at.desc()).first()

        if transaction:
            transaction.sms_text = message.text
            transaction.status = 'pending_verification'
            db.session.commit()

            await message.answer(
                "✅ Deposit SMS received!\n\n"
                "Our team will verify and process your deposit within 30 minutes.\n"
                "You'll receive a notification once it's completed."
            )
        else:
            await message.answer("❌ No pending deposit found. Please start a new deposit.")

        await state.clear()
        await show_main_menu(message)

@router.message(UserState.waiting_for_withdrawal)
async def process_withdrawal_request(message: Message, state: FSMContext):
    """Handle withdrawal amount input"""
    try:
        amount = float(message.text)
        if amount < 100:
            await message.answer("⚠️ Minimum withdrawal amount is 100 birr")
            return

        with app.app_context():
            user = User.query.filter_by(telegram_id=message.from_user.id).first()
            if amount > user.balance:
                await message.answer("⚠️ Insufficient balance")
                return

            # Create withdrawal transaction
            transaction = Transaction(
                user_id=user.id,
                type='withdraw',
                amount=-amount,  # Negative amount for withdrawals
                status='pending',
                withdrawal_phone=user.phone
            )
            db.session.add(transaction)
            db.session.commit()

            await message.answer(
                "✅ Withdrawal request received!\n\n"
                f"Amount: {amount} birr\n"
                "Status: Pending admin approval\n\n"
                "You'll receive a notification once it's processed."
            )
    except ValueError:
        await message.answer("⚠️ Please enter a valid amount")
        return

    await state.clear()
    await show_main_menu(message)

async def main():
    """Main entry point for the bot"""
    try:
        logger.info("Starting bot...")
        bot, dp = await setup_bot()

        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")