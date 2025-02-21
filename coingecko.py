import asyncio
import aiohttp
from dexapi import DexScreenerAPI

class CoinGeckoTerminal:
    def __init__(self):
        self.base_url = "https://api.geckoterminal.com/api/v2"
        self.max_retries = 2
    
    async def get(self, pair_address):
        url = f'{self.base_url}/networks/solana/pools/{pair_address}/trades'
        params = {
            'trade_volume_in_usd_greater_than': 100
        }
        headers = {'accept': 'application/json'}
        for attempt in range(1, self.max_retries + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            print(f"Bad Response: {response.status}")
            except asyncio.TimeoutError:
                print(f"{attempt} timed out")
            except Exception as e:
                print(f"Error as: {e}")


    def save_divide(self, a: float, b: float, default: float = 0.0) -> float:
        try:
            return a / b if b != 0 else default
        except ZeroDivisionError:
            return default

class Main:
    def __init__(self):
        self.c = CoinGeckoTerminal()
        self.d = DexScreenerAPI()
    
    async def run(self):
        data = await self.c.get(pair_address="5ydKnn2h4iiVKzTwZKRqpLCrNkSxKH6wGy9CWGRfrS8w")
        if data:
            print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
