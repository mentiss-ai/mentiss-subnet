"""Test the playRouter.availableModels endpoint against local Mentiss API.

Usage:
    python scripts/test_available_models.py

Requires:
    - Local Mentiss API running on http://localhost:3001
    - Redis running with model pool data seeded
"""

import asyncio
import json
import os
import random
import sys

import httpx

API_URL = os.getenv("MENTISS_API_URL", "http://localhost:3001")
API_KEY = os.getenv("MENTISS_API_KEY", "")


def log(msg: str):
    print(f"[test_available_models] {msg}")


async def main():
    log(f"API URL: {API_URL}")

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    async with httpx.AsyncClient(base_url=API_URL, headers=headers, timeout=30.0) as client:
        # 1. Call the availableModels endpoint
        log("--- Calling playRouter.availableModels ---")
        try:
            resp = await client.get(
                "/api/playRouter.availableModels",
                params={"input": json.dumps({"json": {}})},
            )
            resp.raise_for_status()
            data = resp.json()["result"]["data"]["json"]
        except Exception as e:
            log(f"FAILED: {e}")
            if hasattr(e, "response") and e.response is not None:
                log(f"Response body: {e.response.text}")
            sys.exit(1)

        low_cost = data.get("lowCostModels", [])
        high_perf = data.get("highPerformanceModels", [])

        log(f"lowCostModels ({len(low_cost)}): {low_cost}")
        log(f"highPerformanceModels ({len(high_perf)}): {high_perf}")

        # 2. Validate low-cost models are not empty
        if not low_cost:
            log("WARN: lowCostModels is empty — validator would refuse to start a game")
        else:
            picked = random.choice(low_cost)
            log(f"Random pick from lowCostModels: {picked}")

        # 3. Validate high-performance models
        if not high_perf:
            log("WARN: highPerformanceModels is empty")
        else:
            picked = random.choice(high_perf)
            log(f"Random pick from highPerformanceModels: {picked}")

        # 4. Call multiple times to confirm consistency
        log("--- Calling 3 more times to check consistency ---")
        for i in range(3):
            resp = await client.get(
                "/api/playRouter.availableModels",
                params={"input": json.dumps({"json": {}})},
            )
            resp.raise_for_status()
            d = resp.json()["result"]["data"]["json"]
            lc = d.get("lowCostModels", [])
            hp = d.get("highPerformanceModels", [])
            log(f"  Call {i+1}: lowCost={len(lc)} models, highPerf={len(hp)} models")

    log("--- DONE ---")


if __name__ == "__main__":
    asyncio.run(main())
