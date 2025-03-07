import asyncio
import aiohttp
import requests
from env import BIRDEYE_API_KEY, SOLANA_TRACKER_API_KEY, MORALIS_API_KEY
from dexapi import DexScreenerAPI
from bdmetadata import Tokenomics

class Supply:
    def __init__(self):
        self.rpc_endpoint = "https://api.mainnet-beta.solana.com"

    async def supply(self, ca):
        try:
            funcs = [
                self._rpc_supply,
                self._sol_tracker_supply,
                self._get_birdeye_supply

            ]
            for f in funcs:
                try:
                    supply = await f(ca=ca)
                    if supply is not None:
                        return supply
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Critical Error in Supply fetching: {str(e)}")
            return None

            
            
        except Exception as e:
            print(f"")

    async def _rpc_supply(self, ca):
        payload = {
            "jsonrpc": "2.0", 
            "id": 1,
            "method": "getTokenSupply",
            "params": [ca]
        }
        headers = {'accept': 'application/json'}
        try:
            if not ca:
                print(f"Ca not passed to _rpc_supply function")
                return
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_endpoint,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        print(f"RPC request failed in _rpc_supply function")
                    data = await response.json()
                    if 'error' in data or 'result' not in data or 'value' not in data.get('result', {}):
                        print(f"Error in rpc response: Supply unfetchable (_rpc_supply function)")
                        return None
                    k = float(data['result']['value']['amount'])
                    d = int(data['result']['value']['decimals'])
                    supply = k / (10 ** d)
                    return supply
        except Exception as e:
            print(f"Fatal Error in _rpc_supply func: {str(e)}")
            return None

    async def _get_birdeye_supply(self, ca):
        url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url, headers=headers) as response:
                    if response.status == 200:
                            data = await response.json()
                            if not data:
                                print("No data received from Birdeye Supply")
                                return None   
                            if not isinstance(data, dict):
                                print(f"Invalid Birdeye data format for supply")
                                return None
                            t = data.get('data', {})
                            supply = t.get('supply', 0)
                            if not supply:
                                print(f"Req snt but no spply fnd in bd spply rspnse")
                                return None
                            return supply
        except Exception as e:
            print(f"Fatal Error in BD Supply: {str(e)}")
            return None
    
    async def _sol_tracker_supply(self, ca):
        try:
            url = f"https://data.solanatracker.io/tokens/{ca}"
            headers = {
                'X-API-KEY': SOLANA_TRACKER_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if not data:
                            print(f"Error in Sending req in func: (_sol_tracker_supply)")
                            return None
                        pools = data.get('pools', [])
                        if not pools or len(pools) == 0:
                            print(f"No pools found for {ca} || (_sol_tracker_supply func)")
                            return None
                        supply = pools[0].get('tokenSupply')
                        if not supply:
                            print(f"Error getting supply although pool found")
                            return None
                        return supply
        except Exception as e:
            print(f"Fatal Err in func: (_sol_t_supply): {str(e)}")
            return None


class Price:
    def __init__(self):
        self.dex = DexScreenerAPI()

    async def price(self, ca):
        try:
            funcs = [
                self._cg_price,
                self._dex_price,
                self._bd_price_liquidity,
            ]
            
            for f in funcs:
                try:
                    result = await f(ca=ca)
                    
                    if result is not None:
                        if f == self._bd_price_liquidity:
                            price, _ = result
                            
                            if isinstance(price, str):
                                try:
                                    price = float(price)
                                except (ValueError, TypeError):
                                    print(f"Failed to convert price string to float: {price}")
                                    continue
                            
                            return price
                        else:
                            return result
                except Exception as e:
                    print(f"Error in {f.__name__}: {str(e)}")
                    continue
                    
            print("All price sources failed")
            return None
        except Exception as e:
            print(f"Critical Error in price fetch: {str(e)}")
            return None

    async def _bd_price_liquidity(self, ca):
        try:
            url = f"https://public-api.birdeye.so/defi/price"
            headers = {
                "accept": "application/json",
                "x-chain": "solana",
                "X-API-KEY": BIRDEYE_API_KEY
            }
            params = {
                "include_liquidity": "true",
                "address": ca
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    data = await response.json()
                    if not data:
                        print(f"Error in getting response: _bd_price_liquidity")
                        return None
                    if data.get('success') and 'data' in data:
                        price = data["data"]["value"]
                        liquidity = data["data"]["liquidity"]
                        if not price or not liquidity:
                            print(f"Error in getting price or liq: _bd_price_liqudity")
                        if isinstance(price, float):
                            formatted_price = f"{price:.12f}"  # Show up to 12 decimal places
                            # Remove trailing zeros
                            formatted_price = formatted_price.rstrip('0').rstrip('.') if '.' in formatted_price else formatted_price
                        else:
                            formatted_price = price
                    return formatted_price, liquidity
        except Exception as e:
            print(f"Fatal error in _bd_price_liquidity: {str(e)}")
            return None

    async def _dex_price(self, ca):
        try:
            d = await self.dex.fetch_token_data_from_dex(ca)
            
            if not d:
                print(f"Error in sending req for dex token price - got None")
                return None
                
            if 'price' in d:
                price = d['price']
                
                if isinstance(price, str):
                    price = float(price)
                
                return price
            else:
                print(f"No price key found in response. Available keys: {d.keys()}")
                return None
        except Exception as e:
            print(f"Error in _dex_price: {str(e)}")
            return None
    
    async def _cg_price(self, ca):
        try:
            url = f'https://api.geckoterminal.com/api/v2/simple/networks/solana/token_price/{ca}'
            headers = {'accept': 'application/json'}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data or 'data' not in data:
                        print(f"Error in sending req: _cg_price")
                        return None
                    attributes = data.get('data', {}).get('attributes', {})
                    token_prices = attributes.get('token_prices', {})                    
                    if ca in token_prices:
                        price_str = token_prices[ca]
                        try:
                            price = float(price_str)
                            return price
                        except (ValueError, TypeError):
                            print(f"Failed to convert price string to float: {price_str}")
                            return None
                    else:
                        print(f"Contract address {ca} not found in token_prices")
                        return None
        except Exception as e:
            print(f"{str(e)}")
            return None

class Marketcap:
    def __init__(self):
        self.dex = DexScreenerAPI()
        self.s = Supply()
        self.p = Price()
        self.bdmd = Tokenomics()
    
    async def marketcap(self, ca):
        try:
            d = await self.dex.fetch_token_data_from_dex(ca)
            if d and d.get('token_mc', 0) > 0:
                return d['token_mc']
            s = await self.s.supply(ca)
            p = await self.p.price(ca)
            if s and p:
                mc = s * p
                if mc and mc > 5:
                    return mc
            bdmd = self.bdmd.process(ca)
            if bdmd:
                mc = bdmd.get('marketcap', 0)
                if mc and mc > 0:
                    return mc
            
        except Exception as e:
            print(f"Fatal Error in mc calculation")