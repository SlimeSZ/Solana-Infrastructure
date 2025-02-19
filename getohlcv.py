import requests
import asyncio
import aiohttp
from env import MORALIS_API_KEY
from marketcap import MarketcapFetcher

class OH:
    def __init__(self):
        self.supply = MarketcapFetcher()

    async def fetch(self, timeframe, pair_address):
        url = f"https://solana-gateway.moralis.io/token/mainnet/pairs/{pair_address}/ohlcv"
        params = {
                "timeframe": timeframe,  
                "currency": "usd",
                "fromDate": "2024-11-25",
                "toDate": "2025-11-26",
                "limit": 100
        }
        headers = {
            "Accept": "application/json",
            "X-API-Key": MORALIS_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        return
                    return data
        except Exception as e:
            print(f"{str(e)}")
            return None
        
    async def _supply(self, ca):
        supply = await self.supply.get_token_supply(ca)
        return supply
        
class Main:
    def __init__(self):
        self.o  = OH()
        self.pair_address = "JEHgbWk6RsY6CkuAWRL5yh4RhubTJ3FuhJhYZeA2W2du"
        self.ca = ""
    
    async def run(self):
        await self.o.fetch(pair_address=self.pair_address)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())