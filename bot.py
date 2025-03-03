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

# In-memory storage (will be moved to database)
users = {}
games = {}
available_accounts = [
    {"phone": "0911111111", "name": "Account 1"},
    {"phone": "0922222222", "name": "Account 2"},
    {"phone": "0933333333", "name": "Account 3"},
]

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

    if user_id not in users:
        # New user registration
        users[user_id] = {
            'telegram_id': user_id,
            'username': message.from_user.username,
            'phone': None,
            'balance': 0,
            'referrer_id': referrer_id,
            'games_played': 0,
            'games_won': 0
        }

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
        user = users[user_id]
        await message.answer(
            f"Welcome back to Addis Bingo! 🎮\n\n"
            f"Balance: {user['balance']} birr\n"
            f"Games played: {user['games_played']}\n"
            f"Games won: {user['games_won']}\n\n"
            "Use /deposit to add funds or /play to join a game!",
            reply_markup=ReplyKeyboardRemove()
        )

@router.message(Command("play"))
async def cmd_play(message: Message):
    user_id = message.from_user.id

    if user_id not in users:
        await message.reply("Please register first!")
        return

    # Create a new game if none exists
    game_id = len(games) + 1
    if game_id not in games:
        games[game_id] = BingoGame(game_id)

    game = games[game_id]
    board = game.add_player(user_id)

    if not board:
        await message.reply("Could not join game. It might be full or you're already in it.")
        return

    # Format the board for display
    board_text = "Your Bingo Board:\n\n"
    for i in range(0, 25, 5):
        row = board[i:i+5]
        board_text += " ".join(f"{num:2d}" for num in row) + "\n"

    await message.reply(
        f"You've joined Game #{game_id}\n\n{board_text}\n"
        "Wait for the game to start!"
    )

@router.message(Command("deposit"))
async def cmd_deposit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Please register first using /start")
        return

    # Assign a random deposit account
    account = random.choice(available_accounts)
    await state.set_state(UserState.waiting_for_deposit_sms)
    await state.update_data(deposit_account=account)

    await message.answer(
        "To deposit funds:\n\n"
        f"1. Send money to: {account['phone']}\n"
        f"2. Forward the confirmation SMS to this bot\n\n"
        "⚠️ Important: Only forward SMS from the official bank number!\n"
        "Use /cancel to get a different account."
    )

@router.message(F.contact)
async def process_phone_number(message: Message):
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer("Please share your own contact information.")
        return

    user_id = message.from_user.id
    if user_id not in users:
        await message.answer("Please use /start first!")
        return

    users[user_id]['phone'] = message.contact.phone_number

    # Generate referral link
    bot_info = await bot.me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"

    await message.answer(
        "✅ Registration complete!\n\n"
        f"Your referral link: {referral_link}\n\n"
        "Share this link with friends and earn 20 birr when they:\n"
        "1. Register and verify their phone number\n"
        "2. Make their first deposit\n"
        "3. Play their first game\n\n"
        "Use /deposit to add funds or /play to start playing!",
        reply_markup=ReplyKeyboardRemove()
    )

    if users[user_id]['referrer_id'] and users[user_id]['referrer_id'] in users:
        await bot.send_message(
            users[user_id]['referrer_id'],
            f"🎉 New user {message.from_user.first_name} registered using your referral link!"
        )

async def main():
    # Initialize dispatcher with storage
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())