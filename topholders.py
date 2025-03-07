import asyncio
import aiohttp
import requests
from typing import Dict, Optional, Any
from marketcap import MarketcapFetcher
from tg import WAlletPNL
from env import BIRDEYE_API_KEY
from marketcapfinal import Price, Supply, Marketcap

class HolderAmount:
    def __init__(self):
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2/simple/networks"
        self.limit_bd = 11
        self.holders_data = {}

        self.w = WAlletPNL()
        self.s = Supply()
        self.p = Price()
        self.mc = Marketcap()


    async def get_top_holders(self, ca):
        self.holders_data = {}
        bd_url = f"https://public-api.birdeye.so/defi/v3/token/holder?address={ca}&offset=0&limit={self.limit_bd}"
        
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            response = requests.get(bd_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if not data or 'data' not in data or 'items' not in data['data']:
                print(f"Invalid holder data structure for {ca}")
                return {}
            
            for item in data['data']['items']:
                owner = item['owner']
                amount = float(item['ui_amount'])
                self.holders_data[owner] = amount
            
            return self.holders_data
        except Exception as e:
            print(f"Error getting top holders for {ca}: {str(e)}")
            return {}

    
    async def get_sol_price(self) -> float:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        sol_price = None
        try:
            response = requests.get(url, headers={'accept': 'application/json'})
            response.raise_for_status()
            data = response.json()
            if not data:
                return 200.0
            if 'solana' in data and 'usd' in data['solana']:
                return float(data['solana']['usd'])
        except Exception as e:
            print(F"Error sending GET req => Coin Gecko Main net")
            import traceback
            traceback.print_exc()
            return None        
        
    async def calculate_holder_value(self, ca, price):
        try:
            supply = await self.s.supply(ca)
            sol_price = await self.get_sol_price()
            top_wallet_balance = await self.get_top_holders(ca)
            if not all([supply, price, sol_price, top_wallet_balance]):
                print(f"Missing required data for calculations")
                return {}
                    
            holder_values = {}
            #total_supply = float(supply)
            holders_over_5_percent = []

            # Check only the first/top wallet
            first_wallet = next(iter(top_wallet_balance.items()))
            first_wallet_percentage = (first_wallet[1] / supply) * 100
            
            if first_wallet_percentage >= 8.0:
                del top_wallet_balance[first_wallet[0]]

            # Process all wallets
            total_percentage = 0
            for wallet, balance in top_wallet_balance.items():
                percentage_owned = (balance / supply) * 100
                sol_amount = balance * price
                usd_value = (sol_amount * sol_price) / 200
                total_percentage += percentage_owned
                
                if percentage_owned > 4.99:
                    holders_over_5_percent.append(wallet)
                
                holder_values[wallet] = {
                    "balance": balance,
                    'percentage': round(percentage_owned, 2),
                    'usd_value': round(usd_value, 2)
                }
            
            # Add metadata
            holder_values['metadata'] = {
                'total_percentage_held': round(total_percentage, 2),
                'holders_over_5_percent': len(holders_over_5_percent),
                'concentration_warning': len(holders_over_5_percent) > 0,
                'supply': supply
            }
            
            return holder_values, await self.top_holder_evaluation(holder_values)

        except Exception as e:
            print(f"Error in calculate_holder_value: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    async def top_holder_evaluation(self, holder_data):
        try:
            # Calculate total percentage (excluding metadata)
            total_percentage = holder_data['metadata']['total_percentage_held']
            
            # Output formatting
            #print(f"\nTop Holder Analysis:")
            #print(f"Total Percentage held: {total_percentage}%")
            
            #if holder_data['metadata']['concentration_warning']:
                #print(f"⚠️ Warning: {holder_data['metadata']['holders_over_5_percent']} holders control more than 5% each")
            
            return {
                'total_percentage': total_percentage,
                'high_concentration': holder_data['metadata']['concentration_warning'],
                'high_concentration_count': holder_data['metadata']['holders_over_5_percent'],
            }

            
        except Exception as e:
            print(f"Error calculating total top holder percentage: {str(e)}")
            return None
    
    async def calculate_wallet_pnl(self, holder_data):
        try:
            wallet_pnls = {}
            processed_wallets = 0
            
            # Process top 4 wallets
            for wallet_address in list(holder_data.keys())[:4]:  # Get first 4 wallets
                if wallet_address != 'metadata':  # Skip metadata entry
                    # Get PnL data for this wallet
                    pnl_data = await self.w.calculate_pnl(wallet_address)
                    
                    if pnl_data:
                        wallet_pnls[wallet_address] = {
                            'wallet_pnl': pnl_data['last_100_tx_pnl'],
                            'tokens_traded': pnl_data['tokens_traded'],
                            'wins': pnl_data['tradess_won'],
                            'losses': pnl_data['trades_loss'],
                            'holding_percentage': holder_data[wallet_address]['percentage']
                        }
                        
                        """
                        print(f"\nWallet Analysis for {wallet_address[:8]}...")
                        print(f"PnL: {pnl_data['last_100_tx_pnl']:.4f} SOL")
                        print(f"Tokens Traded: {pnl_data['tokens_traded']}")
                        print(f"Wins/Losses: {pnl_data['tradess_won']}/{pnl_data['trades_loss']}")
                        print(f"Current Holding: {holder_data[wallet_address]['percentage']}%")
                        print("-" * 40)
                        """
            
            # Calculate averages
            if wallet_pnls:
                avg_pnl = sum(w['wallet_pnl'] for w in wallet_pnls.values()) / len(wallet_pnls)
                total_wins = sum(w['wins'] for w in wallet_pnls.values())
                total_losses = sum(w['losses'] for w in wallet_pnls.values())
                
                #print(f"\nTop 4 Wallets Summary:")
                #print(f"Average PnL: {avg_pnl:.4f} SOL")
                #print(f"Total Wins: {total_wins}")
                #print(f"Total Losses: {total_losses}")
                
                return {
                    'wallet_pnls': wallet_pnls,
                    'average_pnl': avg_pnl,
                    'total_wins': total_wins,
                    'total_losses': total_losses
                }
            
            return None

        except Exception as e:
            print(f"Error calculating wallet PnLs: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


