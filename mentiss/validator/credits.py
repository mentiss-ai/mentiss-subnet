"""
Validator Credit Manager — Bulk TAO payment for game infrastructure costs.

Instead of paying per-game (expensive in tx fees), validators purchase
credits in bulk (e.g., 100 games at a time) with a single on-chain transfer.
Each game deducts 1 credit locally. When credits run low, another bulk
purchase is triggered automatically.

Credit balance is persisted to disk so it survives validator restarts.
"""

import os
import json
import time
import bittensor as bt


CREDITS_FILENAME = "game_credits.json"


class CreditManager:
    """Manages game credits purchased via on-chain TAO transfers."""

    def __init__(
        self,
        state_dir: str,
        subtensor: bt.Subtensor,
        wallet: bt.Wallet,
        payment_address: str,
        cost_per_game_tao: float,
        batch_size: int = 100,
        refill_threshold: int = 10,
    ):
        self.state_dir = state_dir
        self.subtensor = subtensor
        self.wallet = wallet
        self.payment_address = payment_address
        self.cost_per_game_tao = cost_per_game_tao
        self.batch_size = batch_size
        self.refill_threshold = refill_threshold

        # Internal state
        self.credits = 0
        self.total_purchased = 0
        self.total_spent_tao = 0.0
        self.last_purchase_time = 0.0

        self._load_state()

    def _state_path(self) -> str:
        return os.path.join(self.state_dir, CREDITS_FILENAME)

    def _load_state(self):
        """Load credit state from disk."""
        path = self._state_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                self.credits = data.get("credits", 0)
                self.total_purchased = data.get("total_purchased", 0)
                self.total_spent_tao = data.get("total_spent_tao", 0.0)
                self.last_purchase_time = data.get("last_purchase_time", 0.0)
                bt.logging.info(
                    f"[Credits] Loaded {self.credits} credits "
                    f"(lifetime: {self.total_purchased} purchased, "
                    f"{self.total_spent_tao:.6f} TAO spent)"
                )
            except Exception as e:
                bt.logging.warning(f"[Credits] Failed to load state: {e}")

    def _save_state(self):
        """Persist credit state to disk."""
        path = self._state_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(
                    {
                        "credits": self.credits,
                        "total_purchased": self.total_purchased,
                        "total_spent_tao": self.total_spent_tao,
                        "last_purchase_time": self.last_purchase_time,
                        "payment_address": self.payment_address,
                        "cost_per_game_tao": self.cost_per_game_tao,
                        "batch_size": self.batch_size,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            bt.logging.error(f"[Credits] Failed to save state: {e}")

    def _purchase_credits(self) -> bool:
        """Purchase a batch of credits via on-chain TAO transfer."""
        amount_tao = self.cost_per_game_tao * self.batch_size

        bt.logging.info(
            f"[Credits] Purchasing {self.batch_size} credits "
            f"({amount_tao:.6f} TAO → {self.payment_address})"
        )

        try:
            balance = self.subtensor.get_balance(
                self.wallet.coldkeypub.ss58_address
            )
            if balance.tao < amount_tao:
                bt.logging.error(
                    f"[Credits] Insufficient balance: {balance} < "
                    f"{amount_tao:.6f} TAO needed for {self.batch_size} credits"
                )
                return False

            result = self.subtensor.transfer(
                wallet=self.wallet,
                destination_ss58=self.payment_address,
                amount=bt.Balance.from_tao(amount_tao),
                wait_for_inclusion=True,
                wait_for_finalization=False,
            )

            if result.success:
                self.credits += self.batch_size
                self.total_purchased += self.batch_size
                self.total_spent_tao += amount_tao
                self.last_purchase_time = time.time()
                self._save_state()

                bt.logging.info(
                    f"[Credits] ✅ Purchased {self.batch_size} credits "
                    f"({amount_tao:.6f} TAO). Balance: {self.credits} credits"
                )
                return True
            else:
                error_msg = getattr(result, "error_message", "unknown error")
                bt.logging.error(
                    f"[Credits] ❌ Transfer failed: {error_msg}"
                )
                return False

        except Exception as e:
            bt.logging.error(f"[Credits] Transfer error: {e}")
            return False

    def use_credit(self) -> bool:
        """
        Try to use 1 credit for a game.

        Returns True if credit was available (or purchased), False if
        no credits could be obtained.
        """
        # Auto-refill when credits are low
        if self.credits <= self.refill_threshold:
            bt.logging.info(
                f"[Credits] Credits low ({self.credits} ≤ {self.refill_threshold}), "
                f"purchasing {self.batch_size} more..."
            )
            if not self._purchase_credits():
                # If purchase fails but we still have some credits, use them
                if self.credits <= 0:
                    return False

        if self.credits <= 0:
            return False

        self.credits -= 1
        self._save_state()
        return True

    def get_balance(self) -> int:
        """Return current credit balance."""
        return self.credits
