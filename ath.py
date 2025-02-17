import asyncio
import aiohttp
import requests
from env import SOLANA_TRACKER_API_KEY

class ATH:
    def __init__(self):
        pass
    async def get_ath(self, ca):
        try:
            url = f"https://data.solanatracker.io/tokens/{ca}/ath"
            headers = {
                'X-API-KEY': SOLANA_TRACKER_API_KEY
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if not data:
                        print(f"Failed to get data")
                        return None
                    ath = data.get('highest_market_cap', 0)
                    if not ath:
                        print(f"Error extracing ath: {response.status}")
                    return ath
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
        
