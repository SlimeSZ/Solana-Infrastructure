from coingecko import CoinGeckoTerminal
import asyncio
import aiohttp
from datetime import datetime
import logging
from collections import defaultdict
import pandas as pd
from env import BIRDEYE_API_KEY
import json
from walletpnl import WAlletPNL
from env import LARGE_BUY_WEBHOOK
from webhooks import TradeWebhook
class Trade_300:
    def __init__(self):
        self.c = CoinGeckoTerminal()
        self.hashes = set()
        self.wallets = set()
        self.botted_wallets = set()
        self.large_buyers = []
        self.large_buys_count = 0
        self.large_sellers = []
        self.large_sells_count = 0
        self.cumulative_trades = 0
        self.wallet_trades = defaultdict(lambda: {
            'first_trade_time': None,
            'last_trade_time': None,
            'buys': {'count': 0, 'total_sol': 0, 'total_usd': 0},
            'sells': {'count': 0, 'total_sol': 0, 'total_usd': 0}
        })

    async def check_wallet_holding(self, ca, wallet_address):
        url = "https://public-api.birdeye.so/v1/wallet/token_balance"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        params = {
            'wallet': wallet_address,
            'token_address': ca
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url, headers=headers, params=params) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            if not data:
                                logging.warning(f"Empty response for wallet {wallet_address}")
                                return None
                                
                            if not isinstance(data, dict):
                                logging.warning(f"Invalid response format for wallet {wallet_address}")
                                return None
                                
                            if not data.get('success'):
                                logging.warning(f"API request unsuccessful for wallet {wallet_address}")
                                return None
                                 
                            token_data = data.get('data', {})
                            if not token_data:
                                logging.warning(f"No token data found for wallet {wallet_address}")
                                return None
                                
                            return {
                                'current_amount': token_data.get('uiAmount', 0),
                                'current_value_usd': token_data.get('valueUsd', 0),
                                'price_usd': token_data.get('priceUsd', 0)
                            }
                        except json.JSONDecodeError as e:
                            logging.error(f"JSON decode error for wallet {wallet_address}: {str(e)}")
                            return None
                    else:
                        logging.warning(f"API returned status {response.status} for wallet {wallet_address}")
                        return None
        except aiohttp.ClientError as e:
            logging.error(f"Network error checking wallet {wallet_address}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error checking wallet {wallet_address}: {str(e)}")
            return None

    async def process_request(self, pair_address, token_ca):
        try:
            raw_data = await self.c.get(pair_address=pair_address)
            if not raw_data or not isinstance(raw_data, dict):
                return None

            data = raw_data.get('data', [])
            if not isinstance(data, list):
                return None

            metrics = {
                'new_buys': {'sol': 0, 'usd': 0, 'count': 0},
                'new_sells': {'sol': 0, 'usd': 0, 'count': 0},
                'total_bought': {'sol': 0, 'usd': 0, 'count': 0},
                'total_sold': {'sol': 0, 'usd': 0, 'count': 0}
            }

            new_trades_count = 0
            for d in data:
                if not isinstance(d, dict):
                    continue
                
                attrs = d.get('attributes', {})
                tx_hash = attrs.get('tx_hash')
                if not tx_hash or tx_hash in self.hashes:
                    continue

                self.hashes.add(tx_hash)
                new_trades_count += 1
                wallet = attrs.get('tx_from_address')
                if not wallet:
                    continue

                tx_kind = attrs.get('kind', 'unknown')
                try:
                    amount_usd = float(attrs.get('volume_in_usd', 0))
                    amount_sol = float(attrs.get('from_token_amount' if tx_kind == 'buy' else 'to_token_amount', 0))
                except (ValueError, TypeError):
                    continue

                timestamp = attrs.get('block_timestamp')
                if not timestamp:
                    continue

                self._update_wallet_trades(wallet, timestamp, tx_kind, amount_sol, amount_usd)
                self._update_metrics(metrics, tx_kind, amount_sol, amount_usd)
                
                if amount_sol > 4:
                    self._track_large_trade(tx_kind, amount_sol, amount_usd, wallet)

            # Update cumulative trades
            self.cumulative_trades += new_trades_count

            # Create DataFrame for analysis
            wallet_data = self._create_wallet_data()
            
            # Get top 5 buyers
            top_5_buyers = wallet_data.nlargest(5, 'buy_sol')[['wallet', 'buy_sol', 'buy_usd']]
            
            # Analyze holdings for top 5 buyers
            top_buyers_analysis = await self.analyze_top_buyers(token_ca, top_5_buyers)

            return {
                'metrics': {
                    'total_trades': self.cumulative_trades,  # Use cumulative count
                    'new_trades': new_trades_count,  # Add new trades count
                    'buy_metrics': {
                        'total_sol': metrics['total_bought']['sol'],
                        'total_usd': metrics['total_bought']['usd'],
                        'count': metrics['total_bought']['count']
                    },
                    'sell_metrics': {
                        'total_sol': metrics['total_sold']['sol'],
                        'total_usd': metrics['total_sold']['usd'],
                        'count': metrics['total_sold']['count']
                    },
                    'sol_net_flow': metrics['total_bought']['sol'] - metrics['total_sold']['sol'],
                    'usd_net_flow': metrics['total_bought']['usd'] - metrics['total_sold']['usd']
                },
                'wallet_analysis': {
                    'total_wallets': len(self.wallets),
                    'botted_wallets': len(self.botted_wallets),
                    'large_trades': {
                        'buys': self.large_buys_count,
                        'sells': self.large_sells_count,
                        'large_buyers': self.large_buyers,
                        'large_sellers': self.large_sellers
                    },
                    'top_5_buyers': top_5_buyers.to_dict('records')  # Convert DataFrame to dict for webhook
                },
                'top_buyers_analysis': top_buyers_analysis.to_dict('records') if top_buyers_analysis is not None else None
            }

        except Exception as e:
            logging.error(f"Error processing request: {str(e)}")
            return None

    def _update_wallet_trades(self, wallet, timestamp, tx_kind, amount_sol, amount_usd):
        if not self.wallet_trades[wallet]['first_trade_time']:
            self.wallet_trades[wallet]['first_trade_time'] = timestamp
        self.wallet_trades[wallet]['last_trade_time'] = timestamp
        
        trade_type = 'buys' if tx_kind == 'buy' else 'sells'
        self.wallet_trades[wallet][trade_type]['count'] += 1
        self.wallet_trades[wallet][trade_type]['total_sol'] += amount_sol
        self.wallet_trades[wallet][trade_type]['total_usd'] += amount_usd

    def _update_metrics(self, metrics, tx_kind, amount_sol, amount_usd):
        if tx_kind == 'buy':
            metrics['new_buys']['sol'] += amount_sol
            metrics['new_buys']['usd'] += amount_usd
            metrics['new_buys']['count'] += 1
            metrics['total_bought']['sol'] += amount_sol
            metrics['total_bought']['usd'] += amount_usd
            metrics['total_bought']['count'] += 1
        elif tx_kind == 'sell':
            metrics['new_sells']['sol'] += amount_sol
            metrics['new_sells']['usd'] += amount_usd
            metrics['new_sells']['count'] += 1
            metrics['total_sold']['sol'] += amount_sol
            metrics['total_sold']['usd'] += amount_usd
            metrics['total_sold']['count'] += 1

    def _track_large_trade(self, tx_kind, amount_sol, amount_usd, wallet):
        trade_data = {
            'amount_sol': amount_sol,
            'amount_usd': amount_usd,
            'wallet': wallet
        }
        if tx_kind == 'buy':
            self.large_buys_count += 1
            self.large_buyers.append(trade_data)
        elif tx_kind == 'sell':
            self.large_sells_count += 1
            self.large_sellers.append(trade_data)

    def _create_wallet_data(self):
        data = []
        for wallet, stats in self.wallet_trades.items():
            data.append({
                'wallet': wallet,
                'first_trade': stats['first_trade_time'],
                'last_trade': stats['last_trade_time'],
                'buy_count': stats['buys']['count'],
                'buy_sol': stats['buys']['total_sol'],
                'buy_usd': stats['buys']['total_usd'],
                'sell_count': stats['sells']['count'],
                'sell_sol': stats['sells']['total_sol'],
                'sell_usd': stats['sells']['total_usd']
            })
        return pd.DataFrame(data)

    async def analyze_top_buyers(self, ca, top_buyers_df):
        holdings_data = []
        for _, buyer in top_buyers_df.iterrows():
            try:
                wallet = buyer['wallet']
                holding_info = await self.check_wallet_holding(ca, wallet)
                
                if holding_info is None:
                    holdings_data.append({
                        'wallet': wallet,
                        'total_invested_sol': float(buyer['buy_sol']),
                        'total_invested_usd': float(buyer['buy_usd']),
                        'current_holding': 0,
                        'current_value_usd': 0,
                        'status': 'exited'
                    })
                else:
                    holdings_data.append({
                        'wallet': wallet,
                        'total_invested_sol': float(buyer['buy_sol']),
                        'total_invested_usd': float(buyer['buy_usd']),
                        'current_holding': holding_info['current_amount'],
                        'current_value_usd': holding_info['current_value_usd'],
                        'status': 'holding'
                    })
            except Exception as e:
                logging.error(f"Error analyzing buyer {wallet}: {str(e)}")
                continue
        
        return pd.DataFrame(holdings_data) if holdings_data else None


async def scan_trades(pair_address, token_name, token_ca, scan_interval):
    trader = Trade_300()
    w = WAlletPNL()
    webhook = TradeWebhook()
    iteration = 0

    # Initialize all tracking variables
    prev_hashes = set()
    prev_large_trades = set()
    # Store PNL data for wallets we've already processed
    wallet_pnl_cache = {}
    
    prev_metrics = {
        'total_trades': 0,
        'buy_sol': 0,
        'sell_sol': 0,
        'large_buys': 0,
        'large_sells': 0
    }
    
    while True:
        try:
            print(f"\n--- Scan Iteration {iteration + 1} ---")
            print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            result = await trader.process_request(pair_address, token_ca)
            
            if result:
                # Calculate new activity
                new_hashes = set(trader.hashes) - prev_hashes
                new_trades = len(new_hashes)
                
                current_large_buys = {(buy['wallet'], buy['amount_sol']) 
                                    for buy in result['wallet_analysis']['large_trades']['large_buyers']}
                current_large_sells = {(sell['wallet'], sell['amount_sol']) 
                                     for sell in result['wallet_analysis']['large_trades']['large_sellers']}
                
                new_large_buys = current_large_buys - prev_large_trades
                new_large_sells = current_large_sells - prev_large_trades
                
                new_metrics = {
                    'total_trades': new_trades,
                    'buy_sol': result['metrics']['buy_metrics']['total_sol'] - prev_metrics['buy_sol'],
                    'sell_sol': result['metrics']['sell_metrics']['total_sol'] - prev_metrics['sell_sol'],
                    'large_buys': len(new_large_buys),
                    'large_sells': len(new_large_sells)
                }
                
                print("\nCumulative Stats:")
                print(f"Total Trades Processed: {len(trader.hashes)}")
                print(f"Net SOL Flow: {result['metrics']['sol_net_flow']:.2f} SOL")
                
                # Prepare data for webhook
                new_buyers_with_pnl = []
                
                # Get unique wallets that need PNL calculation
                unique_new_wallets = {buy['wallet'] for buy in result['wallet_analysis']['large_trades']['large_buyers']
                                    if (buy['wallet'], buy['amount_sol']) in new_large_buys}
                
                # Process large buys
                if new_large_buys:
                    print("\nProcessing New Large Buys...")
                    new_buyers = [buy for buy in result['wallet_analysis']['large_trades']['large_buyers']
                                if (buy['wallet'], buy['amount_sol']) in new_large_buys]
                    
                    # First, get PNL for any new unique wallets
                    for wallet in unique_new_wallets:
                        if wallet not in wallet_pnl_cache:
                            try:
                                print(f"\nGetting PNL for new wallet: {wallet[:8]}...")
                                pnl_result = await w.calculate_pnl(wallet)
                                if pnl_result:
                                    print(f"Got PNL Result for {wallet[:8]}: {pnl_result}")
                                    wallet_pnl_cache[wallet] = pnl_result
                            except Exception as e:
                                print(f"Error getting PNL for {wallet[:8]}: {str(e)}")
                    
                    # Then process all buys, using cached PNL data
                    for buy in new_buyers:
                        wallet = buy['wallet']
                        print(f"\nProcessing buy from: {wallet[:8]}...")
                        
                        buy_data = {
                            'wallet': wallet,
                            'amount_sol': buy['amount_sol'],
                            'amount_usd': buy['amount_usd']
                        }

                        # Use cached PNL data if available
                        if wallet in wallet_pnl_cache:
                            buy_data['pnl_data'] = wallet_pnl_cache[wallet]
                        
                        new_buyers_with_pnl.append(buy_data)
                
                # Process large sells
                if new_large_sells:
                    print("\nProcessing New Large Sells...")
                    new_sellers = [sell for sell in result['wallet_analysis']['large_trades']['large_sellers']
                                 if (sell['wallet'], sell['amount_sol']) in new_large_sells]
                    
                    for sell in new_sellers:
                        print(f"Large sell: {sell['wallet'][:8]}... Amount: {sell['amount_sol']:.2f} SOL")
                
                # Send webhook
                print("\nSending webhook...")
                await webhook.send_trade_webhook(LARGE_BUY_WEBHOOK, result, new_metrics, new_buyers_with_pnl, token_name, ca=token_ca)
                
                # Update tracking sets
                prev_hashes = set(trader.hashes)
                prev_large_trades = current_large_buys | current_large_sells
                prev_metrics = {
                    'total_trades': result['metrics']['total_trades'],
                    'buy_sol': result['metrics']['buy_metrics']['total_sol'],
                    'sell_sol': result['metrics']['sell_metrics']['total_sol'],
                    'large_buys': result['wallet_analysis']['large_trades']['buys'],
                    'large_sells': result['wallet_analysis']['large_trades']['sells']
                }
            
            iteration += 1
            await asyncio.sleep(scan_interval)
            
        except Exception as e:
            logging.error(f"Error in scan iteration: {str(e)}")
            await asyncio.sleep(5)

async def main():
    pair_address = "E1qJzWe8wwtT2c8zg6w6wLwWD4P5fe3ezNB7J8JJE8Go"
    token_ca = "E1qJzWe8wwtT2c8zg6w6wLwWD4P5fe3ezNB7J8JJE8Go"
    
    print("Starting trade scanner...")
    await scan_trades(pair_address, token_ca)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())