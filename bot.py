import os
import logging
import random
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from game_logic import BingoGame
from app import db, User, Game, GameParticipant, active_games

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TOKEN)
router = Router()

# States
class UserState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_deposit_sms = State()
    choosing_cartela = State()

# Game prices
GAME_PRICES = [10, 20, 50, 100]

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = message.get_args()
    referrer_id = None

    # Check if user was referred
    if args:
        try:
            referrer_id = int(args)
            logger.info(f"User {user_id} was referred by {referrer_id}")
        except ValueError:
            logger.warning(f"Invalid referral code: {args}")

    # Check if user exists in database
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        user = User(
            telegram_id=user_id,
            username=message.from_user.username,
            balance=0,
            games_played=0,
            games_won=0
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
    else:
        # Returning user
        await message.answer(
            f"Welcome back to Addis Bingo! 🎮\n\n"
            f"Balance: {user.balance} birr\n"
            f"Games played: {user.games_played}\n"
            f"Games won: {user.games_won}\n\n"
            "Use /play to join a game!",
            reply_markup=ReplyKeyboardRemove()
        )

@router.message(Command("play"))
async def cmd_play(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = User.query.filter_by(telegram_id=user_id).first()

    if not user:
        await message.reply("Please register first using /start")
        return

    # Show game price options
    keyboard = [[KeyboardButton(text=f"{price} Birr")] for price in GAME_PRICES]
    markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

    await state.set_state(UserState.choosing_cartela)
    await message.answer(
        "Choose your game entry price:",
        reply_markup=markup
    )

@router.message(F.contact)
async def process_phone_number(message: Message):
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer("Please share your own contact information.")
        return

    user = User.query.filter_by(telegram_id=message.from_user.id).first()
    if not user:
        await message.answer("Please use /start first!")
        return

    user.phone = message.contact.phone_number
    db.session.commit()

    # Generate referral link
    bot_info = await bot.me()
    referral_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    await message.answer(
        "✅ Registration complete!\n\n"
        f"Your referral link: {referral_link}\n\n"
        "Share this link with friends and earn 20 birr when they:\n"
        "1. Register and verify their phone number\n"
        "2. Make their first deposit\n"
        "3. Play their first game\n\n"
        "Use /play to start playing!",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(UserState.choosing_cartela, F.text.regexp(r"\d+ Birr"))
async def process_game_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.split()[0])
        if price not in GAME_PRICES:
            await message.reply("Invalid game price. Please choose from the available options.")
            return

        # Create or join a game
        game_id = len(active_games) + 1
        if game_id not in active_games:
            active_games[game_id] = BingoGame(game_id, price)

        game = active_games[game_id]

        # Let user choose cartela number
        keyboard = []
        used_cartelas = {p.get('cartela_number', 0) for p in game.players.values()}
        available = [n for n in range(1, 101) if n not in used_cartelas]

        for i in range(0, len(available), 5):
            row = []
            for num in available[i:i+5]:
                row.append(KeyboardButton(text=str(num)))
            if row:
                keyboard.append(row)

        markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        await message.answer(
            "Choose your cartela number (1-100):",
            reply_markup=markup
        )
        await state.update_data(game_id=game_id, price=price)

    except ValueError:
        await message.reply("Invalid input. Please choose a valid game price.")

@router.message(UserState.choosing_cartela, F.text.regexp(r"\d+"))
async def process_cartela_choice(message: Message, state: FSMContext):
    try:
        cartela_number = int(message.text)
        if not 1 <= cartela_number <= 100:
            await message.reply("Please choose a number between 1 and 100.")
            return

        data = await state.get_data()
        game_id = data.get('game_id')
        game = active_games.get(game_id)

        if not game:
            await message.reply("Game not found. Please try again.")
            return

        # Add player with chosen cartela
        board = game.add_player(message.from_user.id, cartela_number)
        if not board:
            await message.reply("Could not join game. The cartela number might be taken.")
            return

        # Format the board for display
        board_text = "Your Bingo Board:\n\n"
        for i in range(0, 25, 5):
            row = board[i:i+5]
            board_text += " ".join(f"{num:2d}" for num in row) + "\n"

        await state.clear()
        await message.reply(
            f"You've joined Game #{game_id}\n\n{board_text}\n"
            "Wait for the game to start!",
            reply_markup=ReplyKeyboardRemove()
        )

    except ValueError:
        await message.reply("Invalid input. Please choose a valid cartela number.")

async def main():
    # Initialize dispatcher with storage
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())