import random
from datetime import datetime
from typing import List, Optional, Tuple

class BingoGame:
    GAME_PRICES = [10, 20, 50, 100]  # in birr
    WINNER_PERCENTAGE = 0.8  # Winner gets 80% of the pool

    def __init__(self, entry_price: float):
        if entry_price not in self.GAME_PRICES:
            raise ValueError("Invalid entry price")

        self.entry_price = entry_price
        self.pool = 0.0
        self.players = {}  # user_id -> cartela_number
        self.called_numbers = []
        self.status = "waiting"
        self.winner_id = None
        self.created_at = datetime.utcnow()
        self.finished_at = None

    def add_player(self, user_id: int, cartela_number: int) -> bool:
        """Add a player to the game with their chosen cartela number."""
        if self.status != "waiting":
            return False
        if cartela_number in self.players.values():
            return False

        self.players[user_id] = cartela_number
        self.pool += self.entry_price
        return True

    def start_game(self) -> bool:
        """Start the game if enough players have joined."""
        if len(self.players) < 2 or self.status != "waiting":
            return False

        self.status = "active"
        return True

    def call_number(self) -> Optional[str]:
        """Call the next random number if the game is active."""
        if self.status != "active":
            return None

        available = [n for n in range(1, 76) if n not in self.called_numbers]
        if not available:
            return None

        number = random.choice(available)
        self.called_numbers.append(number)
        return self.format_number(number)

    @staticmethod
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

    def check_win(self, user_id: int, marked_numbers: List[int]) -> Tuple[bool, str]:
        """Check if a player has won with their marked numbers."""
        if user_id not in self.players or self.status != "active":
            return False, "Invalid player or game not active"

        # Verify all marked numbers have been called
        if not all(num in self.called_numbers for num in marked_numbers):
            return False, "Invalid marked numbers"

        # Check for winning patterns (full house only for now)
        if len(marked_numbers) == 25:  # Full house
            self.winner_id = user_id
            self.status = "finished"
            self.finished_at = datetime.utcnow()
            return True, "BINGO! Full house!"

        return False, "Keep playing"

    def get_winner_prize(self) -> float:
        """Calculate the prize for the winner."""
        return self.pool * self.WINNER_PERCENTAGE if self.winner_id else 0.0