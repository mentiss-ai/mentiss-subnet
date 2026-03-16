import time
import bittensor as bt
from dotenv import load_dotenv

load_dotenv()

from mentiss.base.validator import BaseValidatorNeuron
from mentiss.validator import forward


class Validator(BaseValidatorNeuron):
    def __init__(self, config=None):
        super(Validator, self).__init__(config=config)

        bt.logging.info("load_state()")
        self.load_state()

    async def forward(self):
        return await forward(self)


if __name__ == "__main__":
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
