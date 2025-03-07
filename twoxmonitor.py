import asyncio
import aiohttp
import sqlite3
from datetime import datetime
from webhooks import MultiAlert
from marketcapfinal import Marketcap

class TwoXChecker:
    def __init__(self):
        self.mc = Marketcap()
        self.webhook = MultiAlert()
        self.original_mcs = {}
        self.start_times = {}
        self.achieved_multipliers = {}
        self.monitoring_tasks = {}
    
    async def start_marketcap_monitoring(self, ca, token_name):
        try:
            if ca not in self.monitoring_tasks:
                self.start_times[ca] = datetime.now()
                self.achieved_multipliers[ca] = set()
                task = asyncio.create_task(self.monitor_token_mc(ca, token_name))
                self.monitoring_tasks[ca] = task
        except Exception as e:
            print(f"Error starting mc monitoring... \nerr: {str(e)}")
    
    def calculate_time_elapsed(self, start_time):
        elapsed = datetime.now() - start_time
        hours = elapsed.seconds // 3600
        minutes = (elapsed.seconds % 3600) // 60
        seconds = elapsed.seconds % 60
        return f"{hours}h {minutes}m {seconds}s"
    
    async def update_database(self, ca, hit_2x, multiplier=None):
        """Update database with 2X or other multiplier information"""
        try:
            with sqlite3.connect('memedb.db') as conn:
                cursor = conn.cursor()
                
                # Check if the token exists in the database
                cursor.execute("SELECT id FROM multialerts WHERE ca = ?", (ca,))
                result = cursor.fetchone()
                
                if result:
                    # Update twox column
                    cursor.execute("""
                        UPDATE multialerts 
                        SET twox = ?
                        WHERE ca = ?
                    """, (hit_2x, ca))
                    
                    # If we want to store the specific multiplier, we could add this in a future schema update
                    # For now, we'll just use the boolean twox field
                    
                    conn.commit()
                    print(f"Database updated for {ca}: twox = {hit_2x}")
                else:
                    print(f"Warning: Token {ca} not found in database")
        
        except Exception as e:
            print(f"Error updating database for {ca}: {str(e)}")
    
    async def monitor_token_mc(self, ca, token_name):
        retries = 0
        max_retries = 3
        monitor_count = 0  # Track number of monitoring attempts
        success_count = 0  # Track number of successful multiplier hits
        max_monitors = 30  # Max monitoring attempts before removal
        max_successes = 2  # Max number of successful hits before removal
        hit_2x = False

        while True:
            try:
                monitor_count += 1  # Increment monitor counter
                
                if monitor_count > max_monitors:
                    print(f"\n❌ Removing {token_name} from tracking - Exceeded {max_monitors} checks without hitting target")
                    if ca in self.monitoring_tasks:
                        del self.monitoring_tasks[ca]
                    if ca in self.original_mcs:
                        del self.original_mcs[ca]
                    if ca in self.start_times:
                        del self.start_times[ca]
                    return

                current_mc = await self.mc.marketcap(ca)
                if current_mc is None or current_mc == 0:
                    retries += 1
                    if retries > max_retries:
                        print(f"Stopped Monitoring 2x check for {ca} -- No Valid MC Data from SOL RPC")
                        return
                    await asyncio.sleep(5)
                    continue

                if ca not in self.original_mcs:
                    self.original_mcs[ca] = current_mc
                    print(f"Starting to monitor {token_name}")
                    #print(f"Initial MC: ${current_mc:,.2f}")
                else:
                    original_mc = self.original_mcs[ca]
                    if original_mc > 0:
                        increase_percentage = ((current_mc - original_mc) / original_mc) * 100
                        x_val = (increase_percentage + 100) / 100
                        rounded_x = round(x_val * 2) / 2
                        
                        # Alert on any significant multiplier, regardless of previous alerts
                        if increase_percentage > 90 and rounded_x not in self.achieved_multipliers[ca]:
                            self.achieved_multipliers[ca].add(rounded_x)  # Track this multiplier as achieved
                            success_count += 1  # Increment success counter
                            time_elapsed = self.calculate_time_elapsed(self.start_times[ca])
                            print(f"\n🚀 NEW MILESTONE: {rounded_x}X achieved for {token_name} (Success #{success_count}/2)")
                            print(f"Time taken: {time_elapsed}")
                            print(f"Initial MC: ${original_mc:,.2f}")
                            print(f"Current MC: ${current_mc:,.2f}")
                            print(f"Increase: {increase_percentage:.2f}%")
                            print("-" * 50)
                            
                            # Check if token hit 2X or greater
                            if rounded_x >= 2 and not hit_2x:
                                hit_2x = True
                                # Update database with 2X status
                                await self.update_database(ca, True, rounded_x)
                            
                            await self.webhook.twox_multialert_webhook(
                                token_name=token_name,
                                ca=ca,
                                initial_mc=original_mc,
                                new_mc=current_mc,
                                increase_percentage=increase_percentage,
                                x_val=rounded_x,
                                time_elapsed=time_elapsed
                            )

                            if success_count >= max_successes:
                                print(f"\n✅ Removing {token_name} from tracking - Hit target {max_successes} times successfully!")
                                if ca in self.monitoring_tasks:
                                    del self.monitoring_tasks[ca]
                                if ca in self.original_mcs:
                                    del self.original_mcs[ca]
                                if ca in self.start_times:
                                    del self.start_times[ca]
                                return
                
                await asyncio.sleep(70)
            except Exception as e:
                print(f"Error Monitoring MC for {token_name} ({ca})\nErr: {str(e)}")
                await asyncio.sleep(60)