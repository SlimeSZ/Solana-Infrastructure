import asyncio
import aiohttp
from env import BIRDEYE_API_KEY
import requests
import time

class TrueAge:
    def __init__(self):
        pass

    async def get(self, ca):
        url = f"https://public-api.birdeye.so/defi/txs/token?address={ca}&offset=0&limit=1&tx_type=swap&sort_type=asc"
        headers = {
            'accept': 'application/json',
            'x-chain': 'solana',
            'X-API-KEY': BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        return
                    block_unix_time = data["data"]["items"][0]["blockUnixTime"]
                    current_unix_time = int(time.time())
                    token_age_seconds = current_unix_time - block_unix_time                    
                    token_age_minutes = token_age_seconds // 60
                    
                    return token_age_minutes

        except Exception as e:
            print(str(e))
            return None

class Main:
    def __init__(self):
        self.age = TrueAge()
    
    async def run(self):
        await self.age.get(ca="BTK962Z3Y536kT7V5oTMv52HubhwKHChAuYyfUfpump")

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())