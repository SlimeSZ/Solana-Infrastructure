from getohlcv import OH
from supportresistance import SupportResistance
from dexapi import DexScreenerAPI
from marketcap import MarketcapFetcher
import asyncio
import pandas as pd
import numpy as np
import aiohttp
from datetime import datetime

class OrderBlock:
    def __init__(self):
        self.sr = SupportResistance()  # for helper methods import
        self.o = OH()
        self.d = DexScreenerAPI()
        self.pair_address = None
        self.rpc = MarketcapFetcher()
        self.timeframe = "1min"  # Default timeframe
        self.ca = "GVrtJ5rF34fWwwea4LcEZ7VCWbtb2kEet1oG9BwYpump"
        self.active_obs = []

    async def get_data(self, ca):
        try:
            if not ca:
                print("Error: Contract address not provided")
                return None

            dex_data = await self.d.fetch_token_data_from_dex(ca=ca)
            if not dex_data:
                print("Error: Failed to fetch DEX data")
                return None

            self.pair_address = dex_data.get('pool_address')
            if not self.pair_address:
                print("Error: No pair address found")
                return None

            data = await self.o.fetch(timeframe=self.timeframe, pair_address=self.pair_address)
            
            # Handle internal server error case
            if not data or (isinstance(data, dict) and 'message' in data and 'Internal server error' in data['message']):
                print("Primary OHLCV fetch failed, trying backup source...")
                data = await self.sr.backupohlcv.get(ca)

            if not isinstance(data, dict):
                print("Error: Invalid data format received")
                return None

            print("\nReceived OHLCV data structure:")
            print(f"Data type: {type(data)}")
            print("Data keys:", data.keys() if isinstance(data, dict) else "Not a dictionary")

            return data
        except Exception as e:
            print(f"Error in get_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    async def mark_ob(self, ca, data):
        try:
            print("\n=== Starting mark_ob ===")
            if not ca or not data:
                print("Error: Missing required parameters")
                return None

            supply = await self.rpc.get_token_supply(ca)
            if not supply:
                print("Error: Failed to get token supply")
                return None

            print(f"Got supply: {supply}")
            df = await self.sr._convert(data, supply)
            if df is None:
                print("Error: Data conversion failed")
                return None

            print("\nDataFrame first few rows:")
            print(df.head())

            if not df.empty and all(col in df.columns for col in ['high', 'low']):
                df['high_mc'] = df['high']
                df['low_mc'] = df['low']
                ath = df['high'].max()
                if pd.isna(ath):
                    print("Error: Invalid ATH calculation")
                    return None

                ob_top = []
                ob_bottom = []
                ob_volume = []
                ob_strength = []
                
                print("\n=== Beginning OB Detection ===")
                lookback = 150  # Only look at last 10 candles
                start_idx = max(3, len(df) - lookback)
                print(f"Analyzing last {lookback} candles...")
                
                # Calculate volume moving average
                df['vol_sum_3'] = df['volume'].rolling(window=3, min_periods=1).sum()

                ob_count = 0
                for i in range(start_idx, len(df)-1):
                    print(f"\n--- Analyzing Candle {i} ---")
                    curr_candle = df.iloc[i]
                    prev_candle = df.iloc[i-3:i]
                    next_candle = df.iloc[i+1]
                    
                    curr_vol = curr_candle['volume']
                    prev_vol_mean = prev_candle['volume'].mean()
                    high_vol = curr_vol > prev_vol_mean * 0.1

                    print(f"Current OHLC: {curr_candle['open']:.8f}, {curr_candle['high']:.8f}, {curr_candle['low']:.8f}, {curr_candle['close']:.8f}")
                    print(f"Next Close: {next_candle['close']:.8f}")
                    print(f"Volume Check: {curr_vol:.2f} vs {prev_vol_mean:.2f} (Mean) - High Vol: {high_vol}")
                    print(f"Bullish?: {curr_candle['close'] > curr_candle['open']}")
                    print(f"Breakout?: {next_candle['close'] > curr_candle['high']}")

                    # Check for bullish order block
                    if (next_candle['close'] > curr_candle['high'] 
                        and high_vol and curr_candle['close'] > curr_candle['open']):
                        ob_count += 1
                        print(f"\n🟢 Bullish Order Block #{ob_count} Detected!")
                        print(f"MC Range: ${curr_candle['low']:.8f} - ${curr_candle['high']:.8f}")
                        print(f"Volume: {curr_vol:.2f}")
                        
                        ob_top.append(curr_candle['high'])
                        ob_bottom.append(curr_candle['low'])
                        ob_volume.append(curr_candle['vol_sum_3'])
                        
                        strength = min(curr_vol, prev_vol_mean) / max(curr_vol, prev_vol_mean)
                        ob_strength.append(strength)
                        print(f"OB Strength: {strength:.2%}")

                print(f"\nAnalysis Complete: Found {ob_count} Order Blocks")

                return {
                    'ob_top': ob_top,
                    'ob_bottom': ob_bottom,
                    'ob_volume': ob_volume,
                    'ob_strength': ob_strength,
                    'ob_count': ob_count,
                    'total_candles_analyzed': len(df)-4
                }
            else:
                print("Error: Invalid DataFrame structure")
                return None

        except Exception as e:
            print(f"Error in mark_ob: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    async def monitor_entries(self):
        """Check if MC enters any active order block zones"""
        try:
            current_mc = await self.rpc.calculate_marketcap(ca=self.ca)
            
            for ob in self.active_obs:
                if ob['bottom'] <= current_mc <= ob['top']:
                    print(f"Marketcap in OB zone: {current_mc:.8f}")
                    print(f"OB Range: {ob['bottom']:.8f} - {ob['top']:.8f}")
                    await self.handle_entry(current_mc, ob)
                    
        except Exception as e:
            print(f"Error monitoring entries: {str(e)}")

    async def handle_entry(self, current_mc, order_block):
        try:
            print(f"\n🎯 Entry Triggered at ${current_mc:.8f}")
            print(f"Order Block Range: ${order_block['bottom']:.8f} - ${order_block['top']:.8f}")
            print(f"Order Block Strength: {order_block['strength']:.2%}")
            
            entry_mc = current_mc
            entry_time = datetime.now()
            take_profit = max(entry_mc * 1.5, order_block['top'] * 1.1)  # Higher of 50% gain or 10% above OB top
            stop_loss = entry_mc * 0.5

            while True:
                try:
                    current_mc = await self.rpc.calculate_marketcap(ca=self.ca)
                    current_profit = ((current_mc - entry_mc) / entry_mc) * 100
                    duration = datetime.now() - entry_time
                    
                    print(f"\nCurrent MC: ${current_mc:.8f}")
                    print(f"Entry MC: ${entry_mc:.8f}")
                    print(f"Current Profit: {current_profit:.2f}%")
                    
                    # Take profit conditions
                    if current_mc >= take_profit:
                        print("\n✅ Take Profit Hit!")
                        print(f"Trade Duration: {duration}")
                        print(f"Entry: ${entry_mc:.8f}")
                        print(f"Exit: ${current_mc:.8f}")
                        print(f"Final Profit: {current_profit:.2f}%")
                        return True
                    
                    # Stop loss condition
                    if current_profit <= -50:
                        print("\n❌ Stop Loss Hit!")
                        print(f"Trade Duration: {duration}")
                        print(f"Entry: ${entry_mc:.8f}")
                        print(f"Exit: ${current_mc:.8f}")
                        print(f"Final Loss: {current_profit:.2f}%")
                        return False
                    
                    await asyncio.sleep(45)
                    
                except Exception as e:
                    print(f"Error monitoring trade: {str(e)}")
                    await asyncio.sleep(45)
                    continue
                
        except Exception as e:
            print(f"Error handling entry: {str(e)}")
            return None

    async def run_strategy(self):
        """Main loop combining OB updates and entry monitoring"""
        print(f"\nStarting Order Block strategy for {self.ca}")
        print("Initial order block scan...")
        # Do initial scan right away
        await self.update_order_blocks()
        
        last_ob_update = datetime.now()
        update_interval = 180  # 3 minutes
        
        while True:
            try:
                print("\nChecking conditions...")
                # Check if it's time to update order blocks
                if (datetime.now() - last_ob_update).seconds >= update_interval:
                    print("\nTime to update order blocks...")
                    await self.update_order_blocks()
                    last_ob_update = datetime.now()
                
                # Monitor entries if we have active order blocks
                if self.active_obs:
                    print(f"\nMonitoring {len(self.active_obs)} active order blocks...")
                    await self.monitor_entries()
                else:
                    print("\nNo active order blocks yet...")
                
                await asyncio.sleep(45)
                
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                await asyncio.sleep(45)
        
    async def update_order_blocks(self):
        """Scan for new order blocks and add to active list"""
        data = await self.get_data(ca=self.ca)
        if not data:
            return
            
        result = await self.mark_ob(ca=self.ca, data=data)
        if result and result['ob_count'] > 0:
            # Add new order blocks to active list
            for i in range(result['ob_count']):
                new_ob = {
                    'top': result['ob_top'][i],
                    'bottom': result['ob_bottom'][i],
                    'volume': result['ob_volume'][i],
                    'strength': result['ob_strength'][i],
                    'time_found': datetime.now()
                }
                self.active_obs.append(new_ob)
            print(f"Updated active order blocks - Total: {len(self.active_obs)}")



        
class Main:
    def __init__(self):
        self.ob = OrderBlock()

    async def run(self):
        await self.ob.run_strategy()  # This runs the continuous OB scanning and monitoring

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())