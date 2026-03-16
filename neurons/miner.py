import time
import json
import random
import typing
import bittensor as bt

from mentiss.base.miner import BaseMinerNeuron
from mentiss.protocol import WerewolfSynapse


class Miner(BaseMinerNeuron):
    """
    Mentiss Werewolf miner.

    Reference implementation uses random valid action selection.
    Override _select_action() with LLM-based strategy for competitive play.
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

    async def forward(self, synapse: WerewolfSynapse) -> WerewolfSynapse:
        bt.logging.info(
            f"Game {synapse.game_id} | role={synapse.role} | "
            f"phase={synapse.phase} | sub_phase={synapse.sub_phase} | "
            f"round={synapse.round_number}"
        )

        try:
            pending = json.loads(synapse.pending_action) if synapse.pending_action else {}
        except json.JSONDecodeError:
            bt.logging.error("Failed to parse pending_action")
            synapse.response = None
            return synapse

        options = pending.get("options", [])
        if not options:
            bt.logging.warning("No options available")
            synapse.response = None
            return synapse

        action = self._select_action(synapse, options)
        synapse.response = json.dumps(action)
        bt.logging.info(f"Responding with action: {action}")
        return synapse

    def _select_action(
        self, synapse: WerewolfSynapse, options: list
    ) -> list:
        """
        Select an action from available options.

        Reference implementation: random selection.
        Override this method for smarter strategies (e.g., LLM-based).
        """
        responses = []
        for option in options:
            tag = option.get("tag", "")
            possible_values = option.get("possibleValues", [])
            if possible_values:
                chosen = random.choice(possible_values)
                responses.append({"tag": tag, "value": chosen})
        return responses

    async def blacklist(
        self, synapse: WerewolfSynapse
    ) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return True, "Missing dendrite or hotkey"

        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
            if not self.metagraph.validator_permit[uid]:
                return True, "Non-validator hotkey"

        return False, "Hotkey recognized"

    async def priority(self, synapse: WerewolfSynapse) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            return 0.0
        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        return float(self.metagraph.S[caller_uid])


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
