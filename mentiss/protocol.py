import typing
import bittensor as bt


class WerewolfSynapse(bt.Synapse):
    """
    Synapse for Werewolf game interactions between validator and miner.

    The validator sends game context when it's the miner's turn to act.
    The miner responds with their chosen action.
    """

    # --- Request fields (validator -> miner) ---

    game_id: str = ""
    player_id: str = ""
    role: str = ""
    game_context: str = ""
    pending_action: str = ""
    phase: str = ""
    sub_phase: str = ""
    round_number: int = 0
    system_prompt: str = ""  # Game rules (fetched once per game, passed to miners)

    # --- Response field (miner -> validator) ---

    response: typing.Optional[str] = None

    def deserialize(self) -> typing.Optional[str]:
        return self.response
