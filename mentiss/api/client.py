import os
import json
import httpx
import bittensor as bt
from typing import Optional, List, Dict, Any

from .types import GameSettings, GameStatus, NextInput, HumanPlayer


class MentissAPIClient:
    BASE_URL = "https://api.mentiss.ai"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MENTISS_API_KEY", "")
        if not self.api_key:
            bt.logging.warning("MENTISS_API_KEY not set")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def start_game(self, settings: GameSettings) -> str:
        """Create a new game. Returns gameId."""
        payload = {
            "json": {
                "language": settings.language,
                "gameSetting": settings.game_setting,
                "role": settings.role,
                "hasMemory": settings.has_memory,
                "isHighPerformance": settings.is_high_performance,
            }
        }

        response = await self.client.post(
            "/api/trpc/playRouter.start",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        game_id = data["result"]["data"]["json"]["gameId"]
        bt.logging.info(f"Started game: {game_id}")
        return game_id

    async def get_status(self, game_id: str) -> GameStatus:
        """Poll game state. Returns parsed GameStatus."""
        input_data = json.dumps({"json": {"gameId": game_id}})

        response = await self.client.get(
            "/api/trpc/playRouter.status",
            params={"input": input_data},
        )
        response.raise_for_status()
        raw = response.json()["result"]["data"]["json"]
        return self._parse_status(game_id, raw)

    async def submit_action(
        self,
        game_id: str,
        responses: List[Dict[str, Any]],
        player_id: Optional[str] = None,
    ) -> bool:
        """Submit a player action. Returns success."""
        payload: Dict[str, Any] = {
            "json": {
                "gameId": game_id,
                "responses": responses,
            }
        }
        if player_id:
            payload["json"]["playerId"] = player_id

        response = await self.client.post(
            "/api/trpc/playRouter.submitAction",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["result"]["data"]["json"].get("success", False)

    def _parse_status(self, game_id: str, raw: Dict[str, Any]) -> GameStatus:
        game = raw.get("game", {})

        next_input_raw = raw.get("nextInput")
        next_input = None
        if next_input_raw is not None:
            next_input = NextInput(
                options=next_input_raw.get("options", []),
                prompt=next_input_raw.get("prompt", ""),
                action_id=next_input_raw.get("actionId", ""),
                player_id=next_input_raw.get("playerId", ""),
            )

        human_player_raw = raw.get("humanPlayer")
        human_player = None
        if human_player_raw is not None:
            human_player = HumanPlayer(
                id=human_player_raw.get("id", ""),
                position=human_player_raw.get("position", 0),
                role=human_player_raw.get("role", ""),
                status=human_player_raw.get("status", ""),
            )

        return GameStatus(
            game_id=game_id,
            status=game.get("status", ""),
            winner=game.get("winner"),
            phase=game.get("phase", ""),
            sub_phase=game.get("subPhase", ""),
            current_round=game.get("currentRound", 0),
            players=raw.get("players", []),
            actions=raw.get("actions", []),
            human_log=raw.get("humanLog", ""),
            next_input=next_input,
            human_player=human_player,
            god_log=game.get("godLog", ""),
            summary_log=game.get("summaryLog", ""),
            raw=raw,
        )

    async def close(self):
        await self.client.aclose()
