import requests
import asyncio
import aiohttp
from env import MORALIS_API_KEY
from marketcap import MarketcapFetcher
from marketcapfinal import Supply, Price, Marketcap

class OH:
    def __init__(self):
        pass

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
        
