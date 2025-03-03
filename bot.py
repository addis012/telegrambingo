import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN, ADMIN_IDS
from game_logic import BingoGame, Player

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Game state
current_game = None
players = {}

class UserState(StatesGroup):
    registering = State()
    selecting_cartela = State()
    playing = State()

@dp.message(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in players:
        players[user_id] = Player(
            user_id=user_id,
            username=message.from_user.username,
            balance=0
        )
        await message.reply(
            "Welcome to Bingo Bot! 🎮\n"
            "Use /register to start playing!"
        )
    else:
        await message.reply(
            "Welcome back! 🎮\n"
            "Use /play to join a game or /balance to check your balance."
        )

@dp.message(commands=['register'])
async def cmd_register(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in players:
        await message.reply("You're already registered!")
        return

    await state.set_state(UserState.registering)
    await message.reply(
        "Please send your phone number using the button below:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Share Phone Number", request_contact=True)]],
            resize_keyboard=True
        )
    )

@dp.message(lambda message: message.contact is not None, UserState.registering)
async def process_phone_number(message: types.Message, state: FSMContext):
    if message.contact.user_id == message.from_user.id:
        players[message.from_user.id] = Player(
            user_id=message.from_user.id,
            username=message.from_user.username,
            phone=message.contact.phone_number,
            balance=0
        )
        await state.clear()
        await message.reply(
            "Registration successful! 🎉\n"
            "Use /play to join a game or /deposit to add funds.",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.reply("Please share your own contact information.")

@dp.message(commands=['play'])
async def cmd_play(message: types.Message):
    global current_game
    user_id = message.from_user.id

    if user_id not in players:
        await message.reply("Please /register first!")
        return

    if not current_game:
        current_game = BingoGame()

    if current_game.add_player(players[user_id]):
        cartela_buttons = []
        row = []
        for i in range(1, 101):
            if not current_game.is_cartela_taken(i):
                row.append(types.InlineKeyboardButton(text=str(i), callback_data=f"cartela_{i}"))
                if len(row) == 5:
                    cartela_buttons.append(row)
                    row = []
        if row:
            cartela_buttons.append(row)

        await message.reply(
            "Choose your cartela number (1-100):",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=cartela_buttons)
        )
    else:
        await message.reply("You're already in the game!")

@dp.callback_query(lambda c: c.data and c.data.startswith('cartela_'))
async def process_cartela_selection(callback_query: types.CallbackQuery):
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
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())