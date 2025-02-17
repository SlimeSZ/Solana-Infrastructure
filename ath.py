import asyncio
import aiohttp
import requests
from env import SOLANA_TRACKER_API_KEY

class ATH:
    def __init__(self):
        pass

    async def get_ath(self, ca):
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    await asyncio.sleep(retry_delay * (attempt + 1))

                url = f"https://data.solanatracker.io/tokens/{ca}/ath"
                headers = {
                    'X-API-KEY': SOLANA_TRACKER_API_KEY
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 429:  # Too Many Requests
                            if attempt < max_retries - 1:
                                print(f"Rate limited, retrying in {retry_delay * (attempt + 1)} seconds...")
                                continue
                            
                        response.raise_for_status()
                        data = await response.json()
                        
                        if not data:
                            print(f"Failed to get data")
                            return None
                            
                        ath = data.get('highest_market_cap', 0)
                        if not ath:
                            print(f"Error extracting ath: {response.status}")
                        return ath

            except aiohttp.ClientResponseError as e:
                if e.status == 429 and attempt < max_retries - 1:
                    continue
                print(f"Error fetching ATH for {ca}: {str(e)}")
            except Exception as e:
                print(str(e))
                import traceback
                traceback.print_exc()
                return None

        return None