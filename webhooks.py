# webhooks.py
import asyncio
import aiohttp
from env import ALEF_ALERT_WEBHOOK
from alefalerts import MessageSender  # Remove the () from import

class AlefAlertWebhook:
    def __init__(self):
        self.message_sender = MessageSender()  # Initialize here instead

    async def full_send_ca_to_alefdao(self, ca: str):
        try:
            # First send webhook
            async with aiohttp.ClientSession() as session:
                await session.post(
                    ALEF_ALERT_WEBHOOK,
                    json={'content': 'CA Passed Both Soul Scan & Bundle Bot Check!'}
                )
            print("Sent full pass webhook notification")
            
            # Wait briefly
            await asyncio.sleep(3)
            
            # Then send Discord message
            await self.message_sender.send_message(ca)
            print(f"Sent CA to Discord channel: {ca}")
            
        except Exception as e:
            print(f"Error in full send sequence: {str(e)}")
            import traceback
            traceback.print_exc()

    async def conditional_send_ca_to_alefdao(self, ca: str):
        try:
            # First send webhook
            async with aiohttp.ClientSession() as session:
                await session.post(
                    ALEF_ALERT_WEBHOOK,
                    json={'content': 'CA passed Soul Scanner checker but failed bundle bot check/Bundle Bot down\nTrade w Caution!'}
                )
            print("Sent conditional pass webhook notification")
            
            # Wait briefly
            await asyncio.sleep(3)
            
            # Then send Discord message
            await self.message_sender.send_message(ca)
            print(f"Sent CA to Discord channel: {ca}")
            
        except Exception as e:
            print(f"Error in conditional send sequence: {str(e)}")
            import traceback
            traceback.print_exc()