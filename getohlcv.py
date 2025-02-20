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
                    #print(data)
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
        self.pair_address = "2L6KrgECospS4ot5ccRkSGFvoRPzwcsAhd1TeuJmdV1d"
        self.ca = "HScEFXU7JRZ9XK9GzeLWuaf18d9dr5vcsAyKUbBKpump"
    
    async def run(self):
        data = await self.o.fetch(timeframe="30s", pair_address=self.pair_address)
        if data:
            print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())