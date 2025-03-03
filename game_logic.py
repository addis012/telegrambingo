import random
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Player:
    user_id: int
    username: str
    phone: str = ""
    balance: float = 0.0
    games_played: int = 0
    games_won: int = 0
    referrer_id: Optional[int] = None

class BingoGame:
    def __init__(self):
        self.players: Dict[int, Player] = {}
        self.cartelas: Dict[int, int] = {}  # cartela_number -> user_id
        self.called_numbers: List[int] = []
        self.status = "waiting"  # waiting, active, finished
        self.winner = None
        self.pool = 0
        
    def add_player(self, player: Player) -> bool:
        if player.user_id in self.players:
            return False
        self.players[player.user_id] = player
        return True
        
    def select_cartela(self, user_id: int, number: int) -> bool:
        if number in self.cartelas or user_id not in self.players:
            return False
        self.cartelas[number] = user_id
        return True
        
    def is_cartela_taken(self, number: int) -> bool:
        return number in self.cartelas
        
    def call_number(self) -> Optional[int]:
        if self.status != "active":
            return None
            
        available_numbers = [i for i in range(1, 101) if i not in self.called_numbers]
        if not available_numbers:
            return None
            
        number = random.choice(available_numbers)
        self.called_numbers.append(number)
        return number
        
    def check_win(self, user_id: int, cartela: int) -> bool:
        if cartela not in self.cartelas or self.cartelas[cartela] != user_id:
            return False
        
        if cartela in self.called_numbers:
            self.winner = user_id
            self.status = "finished"
            return True
        return False

    def start_game(self) -> bool:
        if len(self.players) < 2 or self.status != "waiting":
            return False
        self.status = "active"
        return True
        
    def end_game(self):
        if self.winner:
            winner_prize = self.pool * 0.8
            self.players[self.winner].balance += winner_prize
            self.players[self.winner].games_won += 1
            
        for player in self.players.values():
            player.games_played += 1
            
        self.status = "finished"
