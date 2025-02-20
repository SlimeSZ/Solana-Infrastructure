import asyncio
import aiohttp
import pandas as pd
import numpy as np
import pytz
from getohlcv import OH
from marketcap import MarketcapFetcher
from basecg import CoinGeckoTerminal
from datetime import datetime
from collections import defaultdict
import scipy.signal as signal
from env import BIRDEYE_API_KEY
from webhooks import TradeWebhook
from dexapi import DexScreenerAPI
#from scientificnotation import SN

class SupportResistance:
    def __init__(self):
        self.rpc = MarketcapFetcher()
        self.ohlcv = OH()
        self.dex = DexScreenerAPI()
        
        self.timeframe = "1min"
        self.ca = ""
        self.current_mc = None
        self.supply = None

    #helper methods
    async def _set_supply(self, ca):
        supply = await self.rpc.get_token_supply(ca)
        if not supply:
            return None
        return supply
    
    def _price_formatter(self, x: float) -> str:
        return f'{x:.2f}'
    
    def _price_to_mc(self, **kwargs):
        price = kwargs.get('price')
        supply = kwargs.get('supply')
        if price is None or supply is None:
            raise ValueError(f"Both Price & Supply were not provided...")
        # Ensure price is treated as float
        price = float(price)
        return price * supply

    def convert_to_est(self, time):
        utc_dt = pd.to_datetime(time)
        est_tz = pytz.timezone('America/New_York')
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        est_dt = utc_dt.astimezone(est_tz)
        return est_dt
    
    async def _set_mc(self, ca):
        try:
            self.current_mc = await self.rpc.calculate_marketcap(ca)
        except Exception as e:
            print(f"Error setting marketcap {str(e)}")

    async def _convert(self, data, supply):
        df = pd.DataFrame(data['result'])
        
        pd.set_option('display.float_format', lambda x: '{:.20f}'.format(x))
        
        for col in ['open', 'high', 'low', 'close']:
            # Convert scientific notation to decimal
            df[col] = pd.to_numeric(df[col], errors='coerce')
            # Print a sample to verify conversion
            print(f"First {col} value after conversion: {df[col].iloc[0]}")
            # Calculate marketcap
            df[col] = df[col] * supply
            print(f"First {col} marketcap: {df[col].iloc[0]}")
        
        return df
    
    #get resistance & support levels
    async def get_sr(self, data, ca):
        try:
            supply = await self.rpc.get_token_supply(ca)
            if not supply:
                print(f'Error getting supply')
                return None
            self.supply = supply
            await self._set_mc(ca)

            try:
                df = await self._convert(data, supply)
            except Exception as e:
                print(str(e))
                return None

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].apply(self.convert_to_est)
            
            # Don't convert again - use the values from _convert
            df['high_mc'] = df['high']  # Already in marketcap terms
            df['low_mc'] = df['low']    # Already in marketcap terms
            ath = df['high'].max()
            price_range = df['high_mc'].max() - df['low_mc'].min()
            min_prominence = price_range * 0.01
            peak_params = {
                'distance': 2,
                'prominence': min_prominence,
                'width': 1,
                'height': (None, None)
            }
            strong_peaks, _ = signal.find_peaks(df['high_mc'].values, **peak_params)
            strong_troughs, _ = signal.find_peaks(-df['low_mc'].values, **peak_params)
            strong_peak_values = df.iloc[strong_peaks]['high_mc'].values.tolist()
            strong_troughs_values = df.iloc[strong_troughs]['low_mc'].values.tolist()
            temp_r = await self.analyze_sr(strong_peak_values)
            temp_s = await self.analyze_sr(strong_troughs_values)
            resistance_analysis = await self.analyze_sr(strong_peak_values, 
                                                    temp_s['mean'] if temp_s['is_clustered'] else None, 
                                                    is_resistance=True)
            support_analysis = await self.analyze_sr(strong_troughs_values, 
                                                temp_r['mean'] if temp_r['is_clustered'] else None)
            resistance_mean = resistance_analysis['mean']
            support_mean = support_analysis['mean']

            ath_high = ath
            ath_low = ath * 0.90
            final_s = None
            final_r = None

            if resistance_analysis['is_clustered']:
                resistance_mean = resistance_analysis['mean']
                final_r = {
                    'is_clustered': True,
                    'mean': resistance_mean,
                    'range_low': resistance_mean * 0.90,  
                    'range_high': resistance_mean * 1.10  
                }
            else:
                final_r = {
                    'is_clustered': True,
                    'mean': ath,
                    'range_low': ath * 0.90,
                    'range_high': ath * 1.10
                }

            if support_analysis['is_clustered']:
                if support_mean < self.current_mc * 0.30:
                    final_s = support_analysis
            if final_s is None:  # Added this check
                support_mean = np.mean(strong_troughs_values)
                final_s = {
                    'is_clustered': True,
                    'mean': support_mean,
                    'range_low': support_mean * 0.97,
                    'range_high': support_mean * 1.03
                }
            
            resistance_strength = len([x for x in strong_peak_values if abs(x - final_r['mean']) / final_r['mean'] < 0.3]) / len(strong_peak_values) if strong_peak_values else 0
            support_strength = len([x for x in strong_troughs_values if abs(x - final_s['mean']) / final_s['mean'] < 0.3]) / len(strong_troughs_values) if strong_troughs_values else 0
            
            return {
                'resistance': final_r,
                'support': final_s,
                'resistance_strength': resistance_strength,
                'support_strength': support_strength
            }      
        except Exception as e:
            print(f"Fatal Error in get_sr: \n{str(e)}")
            import traceback
            traceback.print_exc()
            return None

    
    async def analyze_sr(self, levels, other_level_mean=None, is_resistance=False):
        if not levels or len(levels) == 0:
            print (f"Insufficient Data Points for calculating support or resistance")
            return {
                'is_clustered': False,
                'mean': None,
                'range_low': None,
                'range_high': None
            }
        levels = [x for x in levels if np.isfinite(x)]
        if not levels or len(levels) < 2:
            return {
                'is_clustered': False,
                'mean': None,
                'range_low': None,
                'range_high': None
            }
        
        mean = np.mean(levels)
        std = np.std(levels)
        similar_threshold = 0.3
        similar_points = [x for x in levels if abs(x - mean) / mean < similar_threshold]

        cluster_mean = np.mean(similar_points) if similar_points else mean
        # Check if we have any similar points
        if not similar_points:
            return {
                'is_clustered': False,
                'mean': mean,
                'range_low': mean * 0.95,
                'range_high': mean * 1.05
            }
        clustering_threshold = 0.5 #need 50% of points to be within 30% marketcap of each other (+-)
        total_points = len(levels)
        total_similar_points = len(similar_points)
        if total_similar_points / total_points >= clustering_threshold:
            cluster_mean = np.mean(similar_points)
            return {
                'is_clustered': True,
                'mean': cluster_mean,
                'range_low': cluster_mean * 0.97, #s/r level is 3% below mean
                'range_high': cluster_mean * 1.03 #& 3% above it
            }
        if other_level_mean is not None:
            distance = abs(cluster_mean - other_level_mean) / other_level_mean
            print(f"Distance from {"support" if not is_resistance else "resistance"} to {"resistance" if is_resistance else "support"} is: {distance:.2f}%")
            if distance < 0.5: #if support & resistance are within 50% of each other
                if is_resistance:
                    return {
                        'is_clustered': True,
                        'mean': cluster_mean,
                        'range_low': cluster_mean * 0.95,
                        'range_high': cluster_mean * 1.05
                    }
                return { #set support range
                    'is_clustered': True,
                    'mean': cluster_mean,
                    'range_low': cluster_mean * 0.97,
                    'range_high': cluster_mean * 1.03
                }
            return { #if levels are already far apart       
                'is_clustered': True,
                'mean': cluster_mean,
                'range_low': cluster_mean * 0.9,
                'range_high': cluster_mean * 1.10
            }
        print(f"Similar Value Cluster not found for support or resistance")
        return {
            'is_clustered': False,
            'mean': mean,
            'range_low': mean * 0.95,
            'range_high': mean * 1.05
        }
    
    async def get_high_vol_zones(self, data, ca):
        try:
            supply = await self.rpc.get_token_supply(ca)
            df = await self._convert(data, supply)
            #df = pd.DataFrame(data['result'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].apply(self.convert_to_est)
            results = []
            #convert to pd to extract individual ohlcv data
            for i in range(len(df)):
                t_est = df['timestamp'].iloc[i]
                o = float(df['open'].iloc[i])
                h = float(df['high'].iloc[i])
                l = float(df['low'].iloc[i])
                c = float(df['close'].iloc[i])
                vl = float(df['volume'].iloc[i])
                results.append({
                    'timestamp': t_est,
                    'open': o,
                    'high': h,
                    'low': l,
                    'close': c,
                    'volume': vl
                })
            result_df = pd.DataFrame(results)
            
            unique_ranges = []
            t10_vol = result_df.nlargest(len(df), 'volume')
            for idx, row in t10_vol.iterrows():
                current_low = row['low']
                current_high = row['high']
                range_exists = False

                for existing_range in unique_ranges:
                    if (abs(current_low - existing_range['low'])/existing_range['low'] < 0.2 and 
                        abs(current_high - existing_range['high'])/existing_range['high'] < 0.2):
                        range_exists = True
                        break
                if not range_exists:
                    unique_ranges.append({
                        'low': current_low,
                        'high': current_high,
                        'volume': row['volume'],
                        'timestamp': row['timestamp']
                    })
            
            print("\n=== Unique Price Ranges (20% Threshold) ===")
            for i, range_data in enumerate(unique_ranges, 1):
                print(f"\nRange #{i}")
                print(f"Time: {range_data['timestamp']}")
                print(f"MC Range: {range_data['low']:.8f} - {range_data['high']:.8f}")
                print(f"Volume: {range_data['volume']:.2f}")
                print("-" * 40)
            
            return unique_ranges
                
            
        except Exception as e:
            print(str(e))
            return None

    async def get_sr_zones(self, ca):
        try:
            """Remove dex data and pass frm bot.py"""
            dex_data = await self.dex.fetch_token_data_from_dex(ca)
            if not dex_data:
                return 
            pair_address = dex_data.get('pool_address')
            if not pair_address:
                return
            data = await self.ohlcv.fetch(timeframe=self.timeframe, pair_address=pair_address)
            if not data:
                return
            if not isinstance(data, dict):
                return
            if 'result' not in data:
                return
            print(f"Analyzing: {len(data['result'])} candles")



            levels = await self.get_sr(data, ca)
            if not levels:
                return
            unique_ranges = await self.get_high_vol_zones(data, ca)
            
            support_zone = levels['support']
            resistance_zone = levels['resistance']
            support_mean = support_zone['mean']
            resistance_mean = resistance_zone['mean']

            volume_support_zones = []
            volume_resistance_zones = []

            for range_data in unique_ranges:
                range_high = range_data['high']
                range_low = range_data['low']
                
                # Check for support zones
                if range_high < support_mean and (range_high / support_mean) > 0.7:
                    volume_support_zones.append(range_data)
                
                # Check for resistance zones
                if range_low > resistance_mean and (range_low / resistance_mean) < 1.3:  # Within 130% of resistance
                    volume_resistance_zones.append(range_data)

            print("\n=== Zone Analysis ===")
            print(f"Main Support Zone: {support_mean:.8f}")
            print(f"Main Resistance Zone: {resistance_mean:.8f}")
            print(f"Volume-based support zones found: {len(volume_support_zones)}")
            print(f"Volume-based resistance zones found: {len(volume_resistance_zones)}")

            if volume_support_zones:
                print("\nPotential Support Zones from Volume:")
                for i, zone in enumerate(volume_support_zones, 1):
                    print(f"\nSupport Zone #{i}")
                    print(f"Range: {zone['low']:.8f} - {zone['high']:.8f}")
                    print(f"Distance from main support: {((zone['high'] - support_mean) / support_mean) * 100:.2f}%")
                    print(f"Volume: {zone['volume']:.2f}")

            if volume_resistance_zones:
                print("\nPotential Resistance Zones from Volume:")
                for i, zone in enumerate(volume_resistance_zones, 1):
                    print(f"\nResistance Zone #{i}")
                    print(f"Range: {zone['low']:.8f} - {zone['high']:.8f}")
                    print(f"Distance from main resistance: {((zone['low'] - resistance_mean) / resistance_mean) * 100:.2f}%")
                    print(f"Volume: {zone['volume']:.2f}")

            return {
                'sr_levels': levels,
                'volume_supports': volume_support_zones,
                'volume_resistances': volume_resistance_zones
            }

        except Exception as e:
            print(f"Error in get_sr_zones: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    async def monitor_price_breakout(self, levels, ath, ca):
        try:
            if not levels or not levels['resistance']:
                print(f"No Resistance levels passed to monitor")
                resistance = ath
            resistance = levels['resistance']
            resistance_high = resistance * 1.05
            resistance_low = resistance * 0.95
            while True:
                current_mc = await self.rpc.calculate_marketcap(ca)
                if current_mc > resistance:
                    print(f"Price broke above resistance")
                    #price breakout webhook here
                    #recursive call to this entire file here
                    break
                await asyncio.sleep(45)
        except Exception as e:
            print(f"Error as {e}")
    
    async def monitor_entry(self, levels, ca):
    #scan in intervals for mc to drop down to support, ensuring support is at least 50% from resistance
    #if price breaks above resistance current,
        # recursively recall everything to get new support resistance zones, repeat
    #exit when price drops below certain threshold
        try:
            if not levels or not levels.get('resistance') or not levels.get('support'):
                print(f"Both Support & Resistance not passed to monitor entry")
                return
            final_resistance = levels['resistance']
            final_support = levels['support']
            if not final_resistance or not final_support:
                return
            
            print(f"\n{"*" * 15}\Watching for entry on: {ca}")
            print(f"Target Entry: ${final_support}")
            print(f"Target TP: ${final_resistance}\n{"*" * 15}\n")

            while True:
                try:
                    current_mc = await self.rpc.calculate_marketcap(ca)
                    is_near_support = (final_support * 0.85) <= current_mc <= (final_support * 1.05)
                    is_50_from_resistance = current_mc <= (final_resistance * 0.5)
                    is_near_resistance = (final_resistance * 0.90) <= current_mc <= (final_resistance * 2)
                    if (is_near_support or is_50_from_resistance):
                        print(f"\nEntry Conditions met: Aped at ${current_mc}")
                        if is_near_support:
                            reason = "Token Dipped to Support Level"
                            print(reason)
                        if is_50_from_resistance:
                            reason = f"Token Dipped 50% from Resistance"
                            print(reason)
                        entry_mc = current_mc
                        entry_time = datetime.now()
                        stop_loss = entry_mc * 0.5
                        while True:
                            current_mc = await self.rpc.calculate_marketcap(ca)
                            current_profit = ((current_mc - entry_mc) / entry_mc) * 100
                            duration = datetime.now() - entry_time
                            print(f"Current MC: ${current_mc}")
                            print(f"Entry MC: ${entry_mc}")
                            print(f"Current Profit: {current_profit:.2f}%")
                            if is_near_resistance:
                                exit_mc = await self.rpc.calculate_marketcap(ca)
                                print(f"Profit Reached")
                                print(f"Trade Duration: {duration}")
                                print(f"Entry: ${entry_mc:.2f}")
                                print(f"Exit: ${exit_mc:.2f}")
                                print(f"Reason: {reason}")
                                print(f"Profit: {current_profit}%")
                            if current_profit <= stop_loss:
                                print(f"Stop Loss Triggered: \nLoss of: {current_profit}%")
                                return
                            await asyncio.sleep(45)
                except Exception as e:
                    print(str(e))
                    return None
        except Exception as e:
            print(str(e))
            return None
        
class Main:
    def __init__(self):
        self.sr = SupportResistance()
        self.ca = "3yZvYfm9D2vCBMFmy6RZtAgJN2PW3gWWfhUM5PeVpump"

    async def run(self):
        try:
            await self.sr.get_sr_zones(ca=self.ca)
        except Exception as e:
            print(f"Error running main class: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
      