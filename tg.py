from telethon import TelegramClient
import asyncio
import aiohttp
from env import API_ID, API_HASH, BOT_WEBHOOK


client = TelegramClient('anon', API_ID, API_HASH)


class SoulScannerBot:
    def __init__(self):
        pass

    async def send_and_receive_message(self, ca: str):
        await client.start()
        await client.send_message('soul_scanner_bot', ca)
        await asyncio.sleep(3)  # Reduced from 5 to 3
    
        messages = await client.get_messages('soul_scanner_bot', limit=1)
        if not messages:
            return False
        print(f"\nReceived message from Soul Scanner for CA: {ca}")
        return await self.process_message(ca, messages[0], return_holder_metrics=True)

    async def process_message(self, ca: str, message, return_holder_metrics=True):
        try:
            if not message.message:
                print("No message content received")
                return False
                
            lines = message.message.split('\n')
            print("\nProcessing Soul Scanner Response:")
            print("-" * 50)
            
            try:
                # Scans
                scans_line = next((line for line in lines if "⚡ Scans:" in line), None)
                if not scans_line:
                    print("❌ Could not find Scans line")
                    return False
                scans = int(scans_line.split("Scans: ")[1].split(" |")[0])
                print(f"✅ Scans: {scans}")
                
                # Fresh wallets
                fresh_line = next((line for line in lines if "First 20:" in line), None)
                if not fresh_line:
                    print("❌ Could not find Fresh wallets line")
                    return False
                fresh = int(fresh_line.split("First 20: ")[1].split(" Fresh")[0])
                print(f"✅ Fresh Wallets: {fresh}")
                
                # Snipers
                sniper_line = next((line for line in lines if "Snipers:" in line), None)
                if not sniper_line:
                    print("❌ Could not find Snipers line")
                    return False
                sniper_percent = float(sniper_line.split("•")[1].strip().split(" ")[0].replace('%', ''))
                print(f"✅ Sniper Percentage: {sniper_percent}%")

                # Holders
                hold_line = next((line for line in lines if "Hodls:" in line), None)
                if not hold_line:
                    print("❌ Could not find Holders line")
                    return False
                holder_count = int(hold_line.split("Hodls: ")[1].split(" •")[0].replace(',', ''))
                top_percentage = float(hold_line.split("Top: ")[1].split("%")[0])
                print(f"✅ Holder Count: {holder_count}")
                print(f"✅ Top Holder Percentage: {top_percentage}%")

                # Dev holdings
                # Dev holdings - Fix the emoji check
                # Dev holdings - Update parser for the new format
                dev_line = next((line for line in lines if "🛠️ Dev:" in line), None)
                if not dev_line:
                    print("❌ Could not find Dev Holdings line")
                    return False
                try:
                    # Parse the new format: "🛠️ Dev: 3 SOL | 62% $PLUS500"
                    dev_percentage = float(dev_line.split("%")[0].split("|")[1].strip())
                    print(f"✅ Dev Holdings: {dev_percentage}%")
                except Exception as e:
                    print(f"❌ Error parsing dev percentage: {e}")
                    print(f"Dev line found: {dev_line}")
                    return False
            
                passes = scans >= 50 and fresh <= 5 and sniper_percent < 50
                print("\nAnalysis Results:")
                print(f"Criteria Check: {'PASSED' if passes else 'FAILED'}")
                print("-" * 50)

                if return_holder_metrics:
                    return {
                        'passes': passes,
                        'holder_count': holder_count,
                        'top_percentage': top_percentage,
                        'dev_holding': dev_percentage,
                        'scans': scans
                    }
            
            except Exception as e:
                print(f"\n❌ Error parsing Soul Scanner response: {str(e)}")
                print("Raw message received:")
                print(message.message)
                return False
            
        except Exception as e:
            print(f"\n❌ Error processing SoulScanner: {e}")
            return False

class BundleBot:
    def __init__(self):
        self.passed_cas = set()


    async def send_and_receive_message(self, ca: str):
       await client.start()
       await client.send_message('TrenchScannerBot', ca)
       await asyncio.sleep(10) 

       messages = await client.get_messages('TrenchScannerBot', limit=1)
       if not messages:
           return None

       
       return await self.process_message(messages[0], ca)
    
    async def process_message(self, message, ca: str):
        try:
            if not message.message:
                return None
                
            if "There was a server error" in message.message:
                print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                await self.conditional_send_ca_to_alefdao(ca)
                return None
                
            lines = message.message.split('\n')
            percentage_lines = [line for line in lines if "Current Held Percentage:" in line]
            if not percentage_lines:
                print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                return None

            percentage_line = percentage_lines[0]  # Now safe to index since we checked if list exists
            holding_percentage = float(percentage_line.split("Current Held Percentage:")[1].strip().replace('%', ''))
            passes = holding_percentage < 30  

            bonded_line = [line for line in lines if "Bonded:" in line]
            if not bonded_line:
                print(f"Bundle bot down but soul scanner criteria met for: {ca}")         
                return None
            
            bonded_l = bonded_line[0]
            bonded_status = bonded_l.split("Bonded:")[1].strip(1)
            print(f"Token On dex?{bonded_status}")
            
            result = {
                'holding_percentage': holding_percentage,
                'passes_criteria': passes,
            }
            
            print(f"Bundle Bot Results:\n{result}")

            if passes:
                if ca not in self.passed_cas:
                    self.passed_cas.add(ca)
            else:
                if ca not in self.passed_cas:
                    self.passed_cas.add(ca)

            return result
            
        except Exception as e:
            print(f"Exception as {e}: Bundle bot down soul scanner criteria met for: {ca}")
            return None

async def main():
    ca = "AsCzbtFHxokNyoJr4xzoXXPmpGdcHnH275sC7frrpump"
    ssbot = SoulScannerBot()
    bndlebot = BundleBot()

    passes_soul = await ssbot.send_and_receive_message(ca)
    if passes_soul:
        print(f"Soul Scanner passed for {ca}")
        bundle_result = await bndlebot.send_and_receive_message(ca)
        if bundle_result:
            print(f"Bundle Bot also passed for {ca}! ")

if __name__ == "__main__":
    asyncio.run(main())
