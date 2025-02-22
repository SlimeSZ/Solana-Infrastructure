import asyncio
from marketcap import MarketcapFetcher
from supportresistance import SupportResistance
from largebuys import scan_trades
from webhooks import TradeWebhook
from env import TRADE_WEBHOOK

class MarketcapMonitor:
    def __init__(self):
        self.rpc = MarketcapFetcher()
        self.sr = SupportResistance()
        self.webhook = TradeWebhook()
        self.monitoring = False
        self.trade_scanner_task = None

    async def start_trade_scanner(self, pair_address, token_ca):
        """Start the trade scanner if not already running"""
        if not self.trade_scanner_task or self.trade_scanner_task.done():
            print("\n🔄 Starting trade scanner...")
            self.trade_scanner_task = asyncio.create_task(scan_trades(pair_address, token_ca))
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

    def is_in_support_zone(self, current_mc, support_mean):
        """Check if current marketcap is in support zone (±5% of support)"""
        support_upper = support_mean * 1.05
        support_lower = support_mean * 0.95
        return support_lower <= current_mc <= support_upper

    async def monitor_marketcap(self, ca, pair_address, age_minutes=180):
        """Monitor marketcap and manage trade scanning"""
        try:
            # Initial SR scan with retries
            print("\n📊 Getting initial SR levels...")
            max_retries = 3
            scan_iterations = 0  # Counter for scan iterations
            MAX_SCANS = 10      # Maximum number of scans
            
            for attempt in range(max_retries):
                try:
                    sr_result = await self.sr.get_sr_zones(ca, age_minutes)
                    if sr_result:
                        break
                    print(f"SR scan attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"Error in SR scan attempt {attempt + 1}: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)

            if not sr_result:
                print("All SR scan attempts failed, terminating...")
                return
            
            support_mean = sr_result['sr_levels']['support']['mean']
            print(f"\n📍 Support level set at: {support_mean:.2f}")
            
            was_in_support = False
            
            while True:
                try:
                    # Get current marketcap
                    current_mc = await self.rpc.calculate_marketcap(ca)
                    if not current_mc:
                        print("Failed to get current marketcap, continuing monitoring...")
                        await asyncio.sleep(60)
                        continue

                    print(f"\n💰 Current MC: {current_mc:.2f}")
                    in_support = self.is_in_support_zone(current_mc, support_mean)

                    if support_mean and current_mc:
                        distance_percentage = ((current_mc - support_mean) / support_mean) * 100
                        print(f"Distance from support: {distance_percentage:.2f}%")

                    # Handle entering support zone
                    if in_support and not was_in_support:
                        print("\n🎯 Entered support zone!")
                        scan_iterations = 0  # Reset counter when entering support zone
                        
                        await self.webhook.send_sr_webhook(TRADE_WEBHOOK, {
                            'event': 'support_zone_entered',
                            'current_mc': current_mc,
                            'support_level': support_mean,
                            'distance_percentage': distance_percentage
                        }, ca)
                        await self.start_trade_scanner(pair_address, ca)

                    # Handle being in support zone
                    elif in_support and was_in_support:
                        scan_iterations += 1
                        print(f"\n📊 Scan iteration {scan_iterations} of {MAX_SCANS}")
                        
                        if scan_iterations >= MAX_SCANS:
                            print("\n🔚 Reached maximum scan iterations, stopping scanner...")
                            await self.stop_trade_scanner()
                            print("Scanner stopped. Terminating program.")
                            return  # Exit the program

                    # Handle leaving support zone
                    elif not in_support and was_in_support:
                        print("\n↗️ Left support zone")
                        await self.webhook.send_sr_webhook(TRADE_WEBHOOK, {
                            'event': 'support_zone_left',
                            'current_mc': current_mc,
                            'support_level': support_mean,
                            'distance_percentage': distance_percentage
                        }, ca)
                        await self.stop_trade_scanner()

                    was_in_support = in_support
                    await asyncio.sleep(60)  # Check every minute

                except Exception as e:
                    print(f"Error in monitoring loop: {str(e)}")
                    await asyncio.sleep(60)

        except Exception as e:
            print(f"Fatal error in monitor_marketcap: {str(e)}")
            if self.trade_scanner_task:
                await self.stop_trade_scanner()

class Main:
    def __init__(self):
        self.monitor = MarketcapMonitor()
        self.ca = "5hbWa39eYiwFdDconNwmTvhxz7tzCd4VsdMFmmpgpump"
        self.pair = "HLSE6DEYYf9eHQwmW4j7R5auswc5sptkFPQCzB3kwvSa"  # Add your pair address

    async def run(self):
        await self.monitor.monitor_marketcap(self.ca, self.pair)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())