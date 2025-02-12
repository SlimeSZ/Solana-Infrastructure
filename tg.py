from telethon import TelegramClient
import asyncio
import aiohttp
import json
from env import API_ID, API_HASH, BOT_WEBHOOK

WEBHOOK_URL = "https://discord.com/api/webhooks/1337649132273139763/39dSEjue0Apj3zTKG5PFU30Kx_l-GqZvrvShT_7cv5NAqB49ubTqolic9_gpAlBUWDKL"
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
        #print(f"\nReceived message from Soul Scanner for CA: {ca}")
        return await self.process_message(ca, messages[0], return_holder_metrics=True)

    async def process_message(self, ca: str, message, return_holder_metrics=True):
        try:
            if not message.message:
                print("No message content received")
                return False
                
            lines = message.message.split('\n')
            #print("\nProcessing Soul Scanner Response:")
            #print("-" * 50)
            
            try:
                # Scans
                scans_line = next((line for line in lines if "⚡ Scans:" in line), None)
                if not scans_line:
                    print("❌ Could not find Scans line")
                    return False
                scans = int(scans_line.split("Scans: ")[1].split(" |")[0])
                #print(f"✅ Scans: {scans}")
                
                # Fresh wallets
                fresh_line = next((line for line in lines if "First 20:" in line), None)
                if not fresh_line:
                    print("❌ Could not find Fresh wallets line")
                    return False
                fresh = int(fresh_line.split("First 20: ")[1].split(" Fresh")[0])
                #print(f"✅ Fresh Wallets: {fresh}")
                
                # Snipers
                sniper_line = next((line for line in lines if "Snipers:" in line), None)
                if not sniper_line:
                    print("❌ Could not find Snipers line")
                    return False
                sniper_percent = float(sniper_line.split("•")[1].strip().split(" ")[0].replace('%', ''))
                #print(f"✅ Sniper Percentage: {sniper_percent}%")

                # Holders
                hold_line = next((line for line in lines if "Hodls:" in line), None)
                if not hold_line:
                    #print("❌ Could not find Holders line")
                    return False
                holder_count = int(hold_line.split("Hodls: ")[1].split(" •")[0].replace(',', ''))
                top_percentage = float(hold_line.split("Top: ")[1].split("%")[0])
                #print(f"✅ Holder Count: {holder_count}")
                #print(f"✅ Top Holder Percentage: {top_percentage}%")

                # Dev holdings
                # Dev holdings - Fix the emoji check
                # Dev holdings - Update parser for the new format
                dev_line = next((line for line in lines if "🛠️ Dev:" in line), None)
                if not dev_line:
                    #print("❌ Could not find Dev Holdings line")
                    return False
                try:
                    # Parse the new format: "🛠️ Dev: 3 SOL | 62% $PLUS500"
                    dev_percentage = float(dev_line.split("%")[0].split("|")[1].strip())
                    #print(f"✅ Dev Holdings: {dev_percentage}%")
                except Exception as e:
                    #print(f"❌ Error parsing dev percentage: {e}")
                    #print(f"Dev line found: {dev_line}")
                    return False
            
                passes = scans >= 50 and fresh <= 5 and sniper_percent < 50
                #print("\nAnalysis Results:")
                #print(f"Criteria Check: {'PASSED' if passes else 'FAILED'}")
                #print("-" * 50)

                if return_holder_metrics:
                    return {
                        'passes': passes,
                        'holder_count': holder_count,
                        'top_percentage': top_percentage,
                        'dev_holding': dev_percentage,
                        'scans': scans
                    }
            
            except Exception as e:
                #print(f"\n❌ Error parsing Soul Scanner response: {str(e)}")
                #print("Raw message received:")
                #print(message.message)
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
                #print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                await self.conditional_send_ca_to_alefdao(ca)
                return None
                
            lines = message.message.split('\n')
            percentage_lines = [line for line in lines if "Current Held Percentage:" in line]
            if not percentage_lines:
                #print(f"Bundle bot down but soul scanner criteria met for: {ca}")
                return None

            percentage_line = percentage_lines[0]  # Now safe to index since we checked if list exists
            holding_percentage = float(percentage_line.split("Current Held Percentage:")[1].strip().replace('%', ''))
            #print(f"Holding: {holding_percentage} %")
            passes = holding_percentage < 30  

            bonded_line = [line for line in lines if "Bonded:" in line]
            if not bonded_line:
                #print(f"Bundle bot down but soul scanner criteria met for: {ca}")         
                return None
            token_on_dex = False
            token_on_pump = False
            try:
                bonded_status = bonded_line[0].split("Bonded:")[1].strip()
                #print(f"Token On dex?{bonded_status}")
                if bonded_status:
                    if bonded_status == "Yes":
                        token_on_dex = True
                    else:
                        token_on_pump = True
            except Exception as e:
                print(str(e))
            
            #print(f"Token has Bonded") if token_on_dex else f"Token on pump"

            
            result = {
                'holding_percentage': holding_percentage,
                'token_bonded': token_on_dex if token_on_dex else token_on_pump,
                'passes': passes
            }
            
            #print(f"Bundle Bot Results:\n{result}")

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
        
class WalletPNL:
    def __init__(self):
        pass

    async def send_and_recieve_message_wallet_pnl(self, wallet_address: str):
        await client.start()
        command = f"/w {wallet_address}"
        await client.send_message('RickBurpBot', command)
        await asyncio.sleep(3)

        messages = await client.get_messages('RickBurpBot', limit=1)
        if not messages:
            return None
        
        return await self.process_wpnl_message(messages[0], wallet_address)

    async def process_wpnl_message(self, message, wallet_address: str):
        try:
            if not message.message:
                return None
                
            lines = message.message.split('\n')
            result = {}
            
            for line in lines:
                # Extract 7D performance
                if "📉 7D:" in line or "📈 7D:" in line:
                    # Extract percentage
                    percentage = float(line.split('%')[0].split(':')[1].strip())
                    # Extract amount
                    amount_str = line.split('[')[1].split(']')[0].strip()
                    # Convert K/M to actual numbers
                    amount = amount_str.replace('K', '000').replace('M', '000000')
                    amount = float(amount.replace('-', '')) * (-1 if '-' in amount_str else 1)
                    
                    result['seven_day_percentage'] = percentage
                    result['seven_day_amount'] = amount
            return result
                    
        except Exception as e:
            print(f"Error processing wallet data: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    async def send_and_recieve_message_dex_paid(self, ca: str):
        await client.start()
        command = f"/dp {ca}"
        await client.send_message('RickBurpBot', command)
        await asyncio.sleep(5)

        messages = await client.get_messages('RickBurpBot', limit=1)
        if not messages:
            return None
        
        return await self.process_dp_message(messages[0], ca)

    async def process_dp_message(self, message, ca: str):
        try:
            if not message.message:
                print("No message content received")
                return None
                
            lines = message.message.split('\n')
            
            # Look for specific indicators in the message
            message_lower = message.message.lower()
            
            # Check for negative indicators
            if "❌" in message.message or "not paid" in message_lower:
                #print(f"DexScreener not paid for CA: {ca}")
                return False
                
            # Check for positive indicators
            if "✅" in message.message or "dexpaid" in message_lower:
                #print(f"DexScreener paid for CA: {ca}")
                return True
                
            # If no clear indicators found, log the uncertainty
            print(f"Unclear DexScreener status for CA: {ca}")
            #print("Message received:", message.message)
            return None
                
        except Exception as e:
            print(f"Error processing DexScreener status: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    async def send_and_recieve_dex_chart(self, ca: str):
        await client.start()
        command = f"/cc {ca}"
        await client.send_message('RickBurpBot', command)
        await asyncio.sleep(10)

        messages = await client.get_messages('RickBurpBot', limit=1)
        if not messages:
            return None
        
        return await self.process_dex_chart_message(messages[0], ca)

    async def process_dex_chart_message(self, message, ca: str):
        try:
            if message and message.media:
                # Get the image bytes
                image_data = await message.download_media(bytes)
                
                # Return both the image data and any message content
                return {
                    'image_data': image_data,
                    'filename': 'chart.jpg',
                    'content_type': 'image/jpeg',
                    'message': message.text if hasattr(message, 'text') else None
                }
            else:
                print(f"No media found in message for CA: {ca}")
                return None
                    
        except Exception as e:
            print(f"Error processing chart message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None




            
        
        
        
    
async def main():
    w = WalletPNL()
    ca = ""
    
    # Get the message with the chart from Telegram
    message = await w.send_and_recieve_dex_chart(ca)
    
    if message:
        # Send the message to Discord webhook
        await w.send_to_discord_webhook(message, ca)
        print("Process completed")
    else:
        print("Failed to get chart from Telegram")

if __name__ == "__main__":
    asyncio.run(main())