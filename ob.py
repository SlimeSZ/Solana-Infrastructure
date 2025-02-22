from getohlcv import OH
from supportresistance import SupportResistance
from dexapi import DexScreenerAPI
from marketcap import MarketcapFetcher
import asyncio
import pandas as pd
import numpy as np
import aiohttp
from webhooks import TradeWebhook
from env import OB_WEBHOOK
from datetime import datetime
from backupsupply import Supply

class OrderBlock:
    def __init__(self):
        self.sr = SupportResistance()  # for helper methods import
        self.o = OH()
        self.d = DexScreenerAPI()
        self.pair_address = None
        self.rpc = MarketcapFetcher()
        self.timeframe = "1min"  # Default timeframe
        self.ca = "7vGQxnACKAogWbSE1uEjdPuEJ5trvqzYVzU2VW42pump"
        self.backup_supply = Supply()
        self.active_obs = []
        self.short_timeframes = ["1min", "30s", "10s", "1s"]
        self.longer_timeframes = ["5min", "10min", "30min", "1h", "1min"]

    async def get_data(self, pair_address, ca, age_minutes=81):
        """Get OHLCV data using appropriate timeframe"""
        try:
            if not ca:
                print("Error: Contract address not provided")
                return None


            data = await self._set_timeframe(pair_address, age_minutes)
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
                print("Error: Failed to get token supply from main, trying backup")
                try:
                    supply = await self.backup_supply.supply(ca)
                except Exception as e:
                    print(str(e))

                

            #print(f"Got supply: {supply}")
            df = await self.sr._convert(data, supply)
            if df is None:
                print("Error: Data conversion failed")
                return None

            #print("\nDataFrame first few rows:")
            #print(df.head())

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
                    #print(f"\n--- Analyzing Candle {i} ---")
                    curr_candle = df.iloc[i]
                    prev_candle = df.iloc[i-3:i]
                    next_candle = df.iloc[i+1]
                    
                    curr_vol = curr_candle['volume']
                    prev_vol_mean = prev_candle['volume'].mean()
                    high_vol = curr_vol > prev_vol_mean * 0.1 #10% more vol than prev candle

                    #print(f"Current OHLC: {curr_candle['open']:.8f}, {curr_candle['high']:.8f}, {curr_candle['low']:.8f}, {curr_candle['close']:.8f}")
                    #print(f"Next Close: {next_candle['close']:.8f}")
                    #print(f"Volume Check: {curr_vol:.2f} vs {prev_vol_mean:.2f} (Mean) - High Vol: {high_vol}")
                    #print(f"Bullish?: {curr_candle['close'] > curr_candle['open']}")
                    #print(f"Breakout?: {next_candle['close'] > curr_candle['high']}")

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
                        ob_tops_sorted = sorted(ob_top)

                #print(f"\nAnalysis Complete: Found {ob_count} Order Blocks")

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
        
    async def _set_timeframe(self, pair_address, age_minutes):
        """
        Set timeframe and try different ones if OB not found.
        Returns OHLCV data from first successful timeframe that finds OBs.
        """
        try:
            timeframes_to_try = self.short_timeframes if age_minutes < 80 else self.longer_timeframes
            
            print(f"\n=== Trying timeframes for {age_minutes} min old token ===")
            print(f"Available timeframes: {timeframes_to_try}")
            
            for tf in timeframes_to_try:
                print(f"\nAttempting timeframe: {tf}")
                self.timeframe = tf
                
                    
                # Get OHLCV data
                data = await self.o.fetch(timeframe=tf, pair_address=pair_address)
                if not data or (isinstance(data, dict) and 'message' in data and 'Internal server error' in data['message']):
                    print(f"Failed to get OHLCV")
                    return None
                    
                if not isinstance(data, dict) or not data:
                    print(f"No valid data for {tf}, trying next timeframe...")
                    continue
                    
                # Try to find OBs with this data
                result = await self.mark_ob(ca=self.ca, data=data)
                if result and result.get('ob_count', 0) > 0:
                    print(f"✅ Found {result['ob_count']} OBs using {tf} timeframe")
                    return data
                else:
                    print(f"No OBs found with {tf}, trying next timeframe...")
                    
            print("❌ No OBs found with any timeframe")
            return None

        except Exception as e:
            print(f"Error in _set_timeframe: {str(e)}")
            return None


    async def run(self, pair_address, token_name):
        """Main loop combining OB updates and entry monitoring"""
        #print(f"\nStarting Order Block strategy for {self.ca}")
        #print("Initial order block scan...")
        # Do initial scan right away
        await self.update_order_blocks(pair_address, token_name)
        
        last_ob_update = datetime.now()
        update_interval = 180  # 3 minutes
        
        while True:
            try:
                #print("\nChecking conditions...")
                # Check if it's time to update order blocks
                if (datetime.now() - last_ob_update).seconds >= update_interval:
                    print("\nTime to update order blocks...")
                    await self.update_order_blocks(pair_address, token_name)
                    last_ob_update = datetime.now()
                
                # Monitor entries if we have active order blocks
                if self.active_obs:
                    print(f"\nMonitoring {len(self.active_obs)} active order blocks...")
                else:
                    print("\nNo active order blocks yet...")
                
                await asyncio.sleep(45)
                
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                await asyncio.sleep(45)
        
    async def update_order_blocks(self, pair_address, token_name):
        """Scan for new order blocks and add to active list"""
        data = await self.get_data(pair_address, ca=self.ca)
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
                
            # Send webhook alert for new OBs
            webhook = TradeWebhook()
            await webhook.send_ob_webhook(OB_WEBHOOK, result, token_name, ca=self.ca)  

    async def monitor_ob_entry(self, token_name, ca, pair_address, current_mc):
        """Check if current marketcap is in any active order block zones"""
        try:
            if not self.active_obs:
                return False
                
            for ob in self.active_obs:
                ob_top = ob['top']
                ob_bottom = ob['bottom']
                
                # Check if current MC is within OB range (give 2% buffer)
                if ob_bottom * 0.98 <= current_mc <= ob_top * 1.02:
                    print(f"\n🎯 Price entered Order Block!")
                    print(f"OB Range: ${ob_bottom:.2f} - ${ob_top:.2f}")
                    print(f"Current MC: ${current_mc:.2f}")
                    print(f"OB Strength: {ob['strength']:.2%}")
                    
                    # Send webhook for OB entry
                    webhook = TradeWebhook()
                    await webhook.send_ob_webhook(OB_WEBHOOK, {
                        'event': 'ob_zone_entered',
                        'current_mc': current_mc,
                        'ob_bottom': ob_bottom,
                        'ob_top': ob_top,
                        'ob_strength': ob['strength'],
                        'volume': ob['volume']
                    }, ca)
                    
                    return True
                    
            return False

        except Exception as e:
            print(f"Error in monitor_ob_entry: {str(e)}")
            return False


        
class Main:
    def __init__(self):
        self.ob = OrderBlock()

    async def run(self):
        await self.ob.run()  # This runs the continuous OB scanning and monitoring

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())