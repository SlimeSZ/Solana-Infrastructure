import asyncio
from marketcap import MarketcapFetcher
from supportresistance import SupportResistance
from largebuys import scan_trades
from webhooks import TradeWebhook
from ob import OrderBlock
from datetime import datetime

class MarketcapMonitor:
    def __init__(self):
        self.rpc = MarketcapFetcher()
        self.sr = SupportResistance()
        self.ob = OrderBlock()
        self.webhook = TradeWebhook()
        self.monitoring = False
        self.trade_scanner_task = None
        self.scan_iterations = 0
        self.MAX_SCANS = 10
        self.active_sr = None
        self.sr_last_update = None
        self.sr_update_interval = 1800  # 30 minutes

    async def initialize(self, token_name, ca, pair_address, age_minutes):
        """Initialize all components concurrently"""
        print("\n=== Initializing Market Monitor ===")
        
        # Start concurrent initialization
        init_tasks = [
            asyncio.create_task(self.update_sr_levels(pair_address, token_name, ca, age_minutes, initial=True)),
            asyncio.create_task(self.ob.update_order_blocks(pair_address, token_name)),
            asyncio.create_task(self.rpc.calculate_marketcap(ca))  # Get initial MC
        ]
        
        results = await asyncio.gather(*init_tasks, return_exceptions=True)
        
        # Process results
        sr_success, ob_success, initial_mc = False, False, None
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Initialization task {i} failed: {str(result)}")
            else:
                if i == 0:  # SR levels
                    sr_success = bool(result)
                elif i == 1:  # OB update
                    ob_success = bool(result)
                else:  # Initial MC
                    initial_mc = result

        print("\n=== Initialization Results ===")
        print(f"{token_name}")
        print(f"SR Levels: {'✅' if sr_success else '❌'}")
        print(f"Order Blocks: {'✅' if ob_success else '❌'}")
        print(f"Initial MC: {'✅' if initial_mc else '❌'} {f'${initial_mc:.2f}' if initial_mc else ''}")
        
        return sr_success or ob_success  # Continue if at least one system is working

    async def update_sr_levels(self, pair_address, token_name, ca, age_minutes, initial=False):
        """Update support and resistance levels with optimized timeframe selection"""
        try:
            if initial:
                print("\n📊 Initial SR level calculation...")
            else:
                print("\n📊 Updating SR levels...")
                
            # First try shorter timeframe for faster response
            self.sr.timeframe = "1min"
            sr_result = await self.sr.get_sr_zones(token_name, ca, pair_address, age_minutes)
            
            if not sr_result and not initial:
                # If update fails, try longer timeframe
                self.sr.timeframe = "5min"
                sr_result = await self.sr.get_sr_zones(token_name, ca, age_minutes)

            if sr_result and 'sr_levels' in sr_result:
                self.active_sr = sr_result['sr_levels']
                self.sr_last_update = datetime.now()
                print(f"Support level updated: ${sr_result['sr_levels']['support']['mean']:.2f}")
                return True
            else:
                print("No valid SR levels found")
                return False
        except Exception as e:
            print(f"Error updating SR levels: {str(e)}")
            return False

    async def monitor_marketcap(self, token_name, ca, pair_address, age_minutes=180):
        """Monitor marketcap for both support and OB entries"""
        try:
            print("\n=== Starting Market Monitor ===")
            self.ob.ca = ca
            self.sr.ca = ca
            
            # Initialize components
            if not await self.initialize(token_name, ca, pair_address, age_minutes):
                print("⚠️ Failed to initialize monitoring components")
                return
            
            monitoring_iteration = 0
            start_time = None
            last_ob_update = datetime.now()
            last_mc_check = datetime.now()
            
            # Intervals (in seconds)
            OB_UPDATE_INTERVAL = 180  # 3 minutes
            MC_CHECK_INTERVAL = 60    # 1 minute
            
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Only perform checks every minute
                    if (current_time - last_mc_check).seconds >= MC_CHECK_INTERVAL:
                        monitoring_iteration += 1
                        print(f"\n=== Monitoring Iteration #{monitoring_iteration} ===")
                        print(f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        last_mc_check = current_time

                        # Concurrent updates for SR and OB when needed
                        update_tasks = []
                        
                        if not self.sr_last_update or (current_time - self.sr_last_update).seconds >= self.sr_update_interval:
                            update_tasks.append(self.update_sr_levels(pair_address, token_name, ca, age_minutes))
                            
                        if (not hasattr(self.ob, 'active_obs') or not self.ob.active_obs) and (current_time - last_ob_update).seconds >= OB_UPDATE_INTERVAL:
                            print("\n🔍 Looking for Order Blocks...")
                            update_tasks.append(self.ob.update_order_blocks(pair_address, token_name))
                            last_ob_update = current_time
                        
                        # Run updates concurrently if needed
                        if update_tasks:
                            await asyncio.gather(*update_tasks, return_exceptions=True)
                        
                        # Get current marketcap
                        current_mc = await self.rpc.calculate_marketcap(ca)
                        if not current_mc:
                            print("❌ Failed to get current marketcap")
                            await asyncio.sleep(MC_CHECK_INTERVAL)
                            continue

                        print(f"\n💰 Current MC: ${current_mc:.2f}")
                        
                        # Check zones and display status
                        print("\n=== Zone Status ===")
                        
                        # Support Zone Check
                        in_support = False
                        if self.active_sr and self.active_sr['support']['mean']:
                            support_mean = self.active_sr['support']['mean']
                            in_support = abs(current_mc - support_mean) / support_mean <= 0.05
                            distance_from_support = ((current_mc - support_mean) / support_mean) * 100
                            print(f"Support Level: ${support_mean:.2f}")
                            print(f"Support Distance: {distance_from_support:.2f}%")
                            print(f"In Support Zone: {'✅' if in_support else '❌'}")
                            
                            if current_mc < (support_mean * 0.35):
                                print("📉 MC dropped below 35% of support level!")
                                await self.stop_trade_scanner()
                                continue
                        else:
                            print("No support level established yet")

                        # Order Block Check
                        in_ob = await self.ob.monitor_ob_entry(token_name, ca, pair_address, current_mc)
                        if hasattr(self.ob, 'active_obs') and self.ob.active_obs:
                            ob_levels = [ob['bottom'] for ob in self.ob.active_obs]
                            if ob_levels:
                                min_ob = min(ob_levels)
                                distance_from_ob = ((current_mc - min_ob) / min_ob) * 100
                                print(f"OB Distance: {distance_from_ob:.2f}%")
                                print(f"In OB Zone: {'✅' if in_ob else '❌'}")
                                
                                if current_mc < (min_ob * 0.35):
                                    print("📉 MC dropped below 35% of lowest OB level!")
                                    await self.stop_trade_scanner()
                                    continue
                        else:
                            print("No active order blocks")

                        # Handle trade scanning
                        if (in_support or in_ob) and not self.monitoring:
                            print("\n🎯 Zone entry detected!")
                            print(f"Reason: {' + '.join(filter(None, ['Support' if in_support else '', 'OB' if in_ob else '']))}")
                            self.scan_iterations = 0
                            start_time = datetime.now()
                            await self.start_trade_scanner(token_name, pair_address, ca)
                        elif self.monitoring:
                            if in_support or in_ob:
                                self.scan_iterations += 1
                                print(f"\n📊 Scan iteration {self.scan_iterations} of {self.MAX_SCANS}")
                                
                                if self.scan_iterations >= self.MAX_SCANS:
                                    print("🔚 Reached maximum scan iterations...")
                                    await self.stop_trade_scanner()
                                    start_time = None
                            else:
                                print("\n📤 Exited all trading zones")
                                await self.stop_trade_scanner()
                                start_time = None

                    await asyncio.sleep(MC_CHECK_INTERVAL)

                except Exception as e:
                    print(f"Error in monitoring loop: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    await asyncio.sleep(MC_CHECK_INTERVAL)

        except Exception as e:
            print(f"Fatal error in monitor_marketcap: {str(e)}")
            if self.trade_scanner_task:
                await self.stop_trade_scanner()

    async def start_trade_scanner(self, token_name, pair_address, token_ca):
        """Start the trade scanner if not already running"""
        if not self.trade_scanner_task or self.trade_scanner_task.done():
            print(f"\n🔄 Starting OB/SR scanner for: {token_name}")
            self.trade_scanner_task = asyncio.create_task(scan_trades(pair_address, token_name, token_ca, scan_interval=60))
            self.monitoring = True

    async def stop_trade_scanner(self):
        """Stop the trade scanner if running"""
        if self.trade_scanner_task and not self.trade_scanner_task.done():
            print("\n⏹️ Stopping trade scanner...")
            self.trade_scanner_task.cancel()
            try:
                await self.trade_scanner_task
            except asyncio.CancelledError:
                pass
            self.monitoring = False

class Main:
    def __init__(self):
        self.monitor = MarketcapMonitor()
        self.ca = None
        self.pair = None

    async def run(self, ca, pair_address):
        self.ca = ca
        self.pair = pair_address
        await self.monitor.monitor_marketcap(self.ca, self.pair)

if __name__ == "__main__":
    main = Main()
    # Example usage:
    ca = "FiY4Diak9i73NAAmaghYDSSPz1QsxE8gtD4o8TWRpump"
    pair = "E1qJzWe8wwtT2c8zg6w6wLwWD4P5fe3ezNB7J8JJE8Go"
    asyncio.run(main.run(ca, pair))