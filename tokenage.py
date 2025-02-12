import requests
import asyncio
from datetime import datetime

class TokenAge:
    def __init__(self):
        self.token_age = None
    
    def reset_age(self):
        self.token_age = None

    async def get_pair_creation_times(self, ca):
        try:
            # Make request to DexScreener API
            url = f"https://api.dexscreener.com/latest/dex/search?q={ca}"
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"Error: API returned status code {response.status_code}")
                return None
                
            data = response.json()
            
            if not data.get('pairs'):
                print("No pairs found")
                return None
                
            # Process each pair
            pair_times = []
            for pair in data['pairs']:
                created_at_ms = pair.get('pairCreatedAt')
                if created_at_ms:
                    # Convert milliseconds to datetime
                    created_at = datetime.fromtimestamp(created_at_ms / 1000)
                    
                    pair_info = {
                        'created_at': created_at,
                        'created_at_timestamp': created_at_ms
                    }
                    pair_times.append(pair_info)
            
            # Sort by creation time
            pair_times.sort(key=lambda x: x['created_at_timestamp'])
            
            return pair_times
            
        except Exception as e:
            print(f"Error in get_pair_creation_times: {str(e)}")
            return None
        
    async def process_pair_age(self, ca):
        age_data = await self.get_pair_creation_times(ca)
        if not age_data or len(age_data) == 0:
            return
        first_pair = age_data[0]
        created_at_timestamp = first_pair['created_at_timestamp']
        
        current_time = datetime.now().timestamp() * 1000
        age_ms = current_time - created_at_timestamp

        seconds = int(age_ms / 1000)
        minutes = seconds // 60
        hours = minutes // 60
        days = hours // 24

        if days > 0:
            return {'value': days, 'unit': 'days'}
        elif hours > 0:
            return {'value': hours, 'unit': 'hours'}
        elif minutes > 0:
            return {'value': minutes, 'unit': 'minutes'}
        else:
            return {'value': seconds, 'unit': 'seconds'}


class Main:
    def __init__(self):
        self.r = TokenAge()
    
    async def run(self):
        await self.r.process_pair_age()


if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
