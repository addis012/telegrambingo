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
deposits = {}
available_accounts = [
    {"phone": "0911111111", "name": "Account 1"},
    {"phone": "0922222222", "name": "Account 2"},
    {"phone": "0933333333", "name": "Account 3"},
]

current_game = None  # Global game variable

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

@router.message(UserState.waiting_for_deposit_sms)
async def process_deposit_sms(message: Message, state: FSMContext):
    if not message.forward_date:
        await message.answer("Please forward the SMS, don't type it manually!")
        return

    # Here we'll add SMS verification logic
    # For now, we'll simulate successful deposit
    data = await state.get_data()
    account = data.get('deposit_account')

    if account:
        # Simple SMS parsing (to be enhanced with actual Tasker data)
        user_id = message.from_user.id
        deposit_amount = 100  # This will be parsed from actual SMS

        users[user_id]['balance'] += deposit_amount

        # Record the deposit
        if user_id not in deposits:
            deposits[user_id] = []
        deposits[user_id].append({
            'amount': deposit_amount,
            'account': account['phone'],
            'timestamp': message.date
        })

        await state.clear()
        await message.answer(
            f"✅ Deposit successful!\n\n"
            f"Amount: {deposit_amount} birr\n"
            f"New balance: {users[user_id]['balance']} birr\n\n"
            "Use /play to start playing!"
        )

        # Check if this is the user's first deposit and they were referred
        if len(deposits[user_id]) == 1 and users[user_id]['referrer_id']:
            referrer_id = users[user_id]['referrer_id']
            if referrer_id in users:
                # Add bonus to referrer
                users[referrer_id]['balance'] += 20
                await bot.send_message(
                    referrer_id,
                    f"🎉 You received 20 birr bonus!\n"
                    f"Your referral {message.from_user.first_name} made their first deposit."
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

# Game-related imports and handlers
from game_logic import BingoGame, Player

@router.message(Command("play"))
async def cmd_play(message: Message):
    global current_game
    user_id = message.from_user.id

    if user_id not in users:
        await message.reply("Please register first!")
        return

    if not current_game:
        current_game = BingoGame()

    player = Player(user_id=user_id, username=users[user_id]['username'])
    if current_game.add_player(player):
        cartela_buttons = []
        row = []
        for i in range(1, 101):
            if not current_game.is_cartela_taken(i):
                row.append(InlineKeyboardButton(text=str(i), callback_data=f"cartela_{i}"))
                if len(row) == 5:
                    cartela_buttons.append(row)
                    row = []
        if row:
            cartela_buttons.append(row)

        await message.reply(
            "Choose your cartela number (1-100):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=cartela_buttons)
        )
    else:
        await message.reply("You're already in the game!")

@router.callback_query(lambda c: c.data and c.data.startswith('cartela_'))
async def process_cartela_selection(callback_query: CallbackQuery):
    cartela_number = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id

    if current_game and current_game.select_cartela(user_id, cartela_number):
        await callback_query.answer(f"You selected cartela {cartela_number}")
        await bot.send_message(
            user_id,
            f"Your cartela number is {cartela_number}\n"
            "Wait for the game to start!"
        )
    else:
        await callback_query.answer("This cartela is already taken!")

async def main():
    # Initialize dispatcher with storage
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())