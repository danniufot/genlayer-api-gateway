# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
WeatherBet — Example contract that consumes ApiGateway
=======================================================
Demonstrates how another Intelligent Contract can call the
ApiGateway library to get live weather data and execute logic
based on it — without ever touching an API key directly.

Deployment args:
  gateway_address (Address) — deployed ApiGateway contract address
"""

from genlayer import *
import json


class WeatherBet(gl.Contract):
    """
    A simple weather-conditional bet:
    Users predict whether it will be above 25°C in a city.
    The contract resolves by querying the ApiGateway.
    """

    gateway: Address
    bets: TreeMap[Address, bool]   # True = bet "hot" (>25°C), False = bet "cold"
    resolved: bool
    city: str
    winner_side: bool              # True = hot won, False = cold won

    def __init__(self, gateway_address: Address, city: str) -> None:
        self.gateway = gateway_address
        self.bets = TreeMap()
        self.resolved = False
        self.city = city
        self.winner_side = False

    @gl.public.write
    def place_bet(self, hot: bool) -> None:
        """Place a bet. True = above 25°C, False = 25°C or below."""
        if self.resolved:
            raise gl.vm.UserError("Bet already resolved")
        self.bets[gl.message.sender_address] = hot

    @gl.public.write
    def resolve(self) -> str:
        """
        Resolve the bet by fetching live weather via ApiGateway.
        Uses LLM-analysis endpoint for a natural-language verdict.
        """
        if self.resolved:
            raise gl.vm.UserError("Already resolved")

        # Call the gateway contract — key stays inside gateway
        gateway_contract = gl.get_contract(self.gateway)

        answer: str = gateway_contract.analyze_api_data(
            "weather",
            f"/weather?q={self.city}&units=metric",
            "What is the current temperature in Celsius? Reply with just the number.",
        )

        def parse_temp() -> bool:
            try:
                temp = float(answer.strip())
                return temp > 25.0
            except ValueError:
                raise gl.vm.UserError(f"Could not parse temperature from: {answer}")

        is_hot: bool = gl.eq_principle_strict_eq(parse_temp)

        self.winner_side = is_hot
        self.resolved = True
        return f"Resolved: {'Hot' if is_hot else 'Cold'} (temp={answer}°C)"

    @gl.public.view
    def did_i_win(self, player: Address) -> str:
        """Check if a player's bet won after resolution."""
        if not self.resolved:
            return "Not yet resolved"
        if player not in self.bets:
            return "No bet found"
        bet = self.bets[player]
        won = bet == self.winner_side
        return "Winner!" if won else "Better luck next time."

    @gl.public.view
    def get_status(self) -> dict:
        return {
            "city": self.city,
            "resolved": self.resolved,
            "winner_side": "hot" if self.winner_side else "cold",
        }
