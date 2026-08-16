import asyncio
import json

import httpx


async def main():
    base = "http://localhost:8000"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{base}/api/supervisors",
            json={
                "name": "Demo Supervisor",
                "base_instruction": (
                    "You are an order supervisor. Monitor order health, keep the "
                    "customer informed, and escalate payment or shipping problems "
                    "quickly."
                ),
                "available_actions": [
                    "message_customer",
                    "message_fulfillment_team",
                    "message_payments_team",
                    "message_logistics_team",
                    "create_internal_note",
                ],
                "wakeup_aggressiveness": "medium",
            },
        )
        print(r.status_code, r.text)
        r.raise_for_status()
        # the supervisor id is generated server-side (supervisor-<uuid>), so
        # grab it from the response instead of guessing it
        supervisor_id = r.json()["id"]

        run = await client.post(
            f"{base}/api/runs",
            json={"order_id": "ORD-10423", "supervisor_id": supervisor_id},
        )
        print(run.status_code, run.text)


if __name__ == "__main__":
    asyncio.run(main())
