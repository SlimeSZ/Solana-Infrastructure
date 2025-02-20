import asyncio
import aiohttp
from env import SOLANA_TRACKER_API_KEY

class OHLCV:
    def __init__(self):
        pass

    async def get(self, ca):
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    await asyncio.sleep(retry_delay * (attempt + 1))

                url = f"https://data.solanatracker.io/chart/{ca}"
                headers = {
                    'X-API-KEY': SOLANA_TRACKER_API_KEY
                }
                params = {
                    'type': '1m'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status == 429:  # Too Many Requests
                            if attempt < max_retries - 1:
                                print(f"Rate limited, retrying in {retry_delay * (attempt + 1)} seconds...")
                                continue
                            
                        response.raise_for_status()
                        data = await response.json()
                        
                        if not data:
                            print(f"Failed to get data")
                            return None
                        #print(data)
                            
                        return data

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
    
class Main:
    def __init__(self):
        self.o = OHLCV()
    async def run(self):
        await self.o.get(ca="3xg8g3dpiMNGiKNVMiYZ1tDhhXgVoY1psmmYroW7pump")

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())