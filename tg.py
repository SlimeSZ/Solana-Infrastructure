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
            
            try:
                # Initialize default values
                scans = 0
                fresh = 0
                sniper_percent = 0
                holder_count = 0
                top_percentage = 0
                dev_percentage = 0

                # Scans - Optional
                scans_line = next((line for line in lines if "⚡ Scans:" in line), None)
                if scans_line:
                    scans = int(scans_line.split("Scans: ")[1].split(" |")[0])
                
                # Fresh wallets - Optional
                fresh_line = next((line for line in lines if "First 20:" in line), None)
                if fresh_line:
                    fresh = int(fresh_line.split("First 20: ")[1].split(" Fresh")[0])
                
                # Snipers - Optional
                sniper_line = next((line for line in lines if "Snipers:" in line), None)
                if sniper_line:
                    try:
                        sniper_percent = float(sniper_line.split("•")[1].strip().split(" ")[0].replace('%', ''))
                    except:
                        sniper_percent = 0

                # Holders - Required
                hold_line = next((line for line in lines if "Hodls:" in line), None)
                if not hold_line:
                    return False
                holder_count = int(hold_line.split("Hodls: ")[1].split(" •")[0].replace(',', ''))
                top_percentage = float(hold_line.split("Top: ")[1].split("%")[0])

                # Dev holdings - Required
                dev_line = next((line for line in lines if "🛠️ Dev:" in line), None)
                if not dev_line:
                    return False
                try:
                    dev_percentage = float(dev_line.split("%")[0].split("|")[1].strip())
                except:
                    dev_percentage = 0
            
                # Determine if passes based on available data
                passes = True
                if scans_line:  # Only check scans if we have the data
                    passes = passes and scans >= 50
                if fresh_line:  # Only check fresh if we have the data
                    passes = passes and fresh <= 5
                if sniper_line:  # Only check snipers if we have the data
                    passes = passes and sniper_percent < 50

                if return_holder_metrics:
                    return {
                        'passes': passes,
                        'holder_count': holder_count,
                        'top_percentage': top_percentage,
                        'dev_holding': dev_percentage,
                        'scans': scans
                    }
            
            except Exception as e:
                print(f"Warning: Some data could not be parsed from Soul Scanner response: {str(e)}")
                # Return partial data if we have the essential metrics
                if holder_count and dev_percentage:
                    return {
                        'passes': True,  # Default to True if we can't check all criteria
                        'holder_count': holder_count,
                        'top_percentage': top_percentage,
                        'dev_holding': dev_percentage,
                        'scans': scans
                    }
                return False
            
        except Exception as e:
            print(f"Error processing SoulScanner: {e}")
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