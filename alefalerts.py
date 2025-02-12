import asyncio
from env import DISCORD_AUTH_TOKEN, ALEF_ALERT_CHANNEL_ID
import aiohttp

class MessageSender:
    def __init__(self):
        self.token = DISCORD_AUTH_TOKEN
        self.channel_id = ALEF_ALERT_CHANNEL_ID
        self.base_url = 'https://discord.com/api/v9'
        self.headers = {
            'Authorization': self.token,  
            'Content-Type': 'application/json'
        }

    async def send_message(self, content: str):
        url = f'{self.base_url}/channels/{self.channel_id}/messages'
        payload = {'content': content}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    response_text = await response.text()
                    print(f"Response status: {response.status}")
                    print(f"Response body: {response_text}")
                    
                    if response.status == 200:
                        print(f"Successfully sent message: {content}")
                    else:
                        print(f"Failed to send message. Status: {response.status}")
                        print(f"Error details: {response_text}")
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            import traceback
            traceback.print_exc()

