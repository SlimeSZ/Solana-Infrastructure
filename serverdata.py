import asyncio
import discord
from discord.ext import commands
from process_descriptions import TX_ANALYZER
from env import DISCORD_BOT_TOKEN

intents = discord.Intents.all()
intents.message_content = True
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

class ServerData:
    def __init__(self, bot):
        self.bot = bot
        self.tx = TX_ANALYZER()
        self.target_ca = None
        #server counts
        self.swt_count = 0
        self.degen_count = 0
        self.fresh_count = 0
        #buy sell data
        self.swt_buy_amount = 0
        self.swt_sell_amount = 0
        self.degen_buy_amount = 0
        self.degen_sell_amount = 0
        self.fresh_buy_amount = 0
        self.fresh_sell_amount = 0

        self.swt_channel_ids = [
            1273250694257705070,  # whale  
            1280465862163304468,  # smart
            1279040666101485630,  # legend
            1280445495482781706,  # kol alpha
            1273245344263569484,  # kol reg
            1283348335863922720,  # challenge
            1273670414098501725,  # high freq
            1277231510574862366   # insider
        ]
        self.degen_channel_id = 1278278627997384704
        self.fresh_channel_ids = [
            1281675800260640881,  # fresh
            1281676746202026004,  # 5sol1m mc
            1281677424005746698   # fresh 1h
        ]

        
        

    def reset_counts(self):
        self.swt_count = 0
        self.degen_count = 0
        self.fresh_count = 0
        self.swt_buy_amount = 0
        self.swt_sell_amount = 0
        self.degen_buy_amount = 0
        self.degen_sell_amount = 0
        self.fresh_buy_amount = 0
        self.fresh_sell_amount = 0
        
    async def swt_server_data(self):
        if not self.target_ca:
            return
            
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': [],
            'trading_links': {
                'photon': None,
                'dex': None,
                'bull_x': None
            }
        }
        
        for channel_id in self.swt_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    
                    retry_count = 0
                    max_retries = 3
                    
                    while retry_count < max_retries:
                        try:
                            async for message in channel.history(limit=2):
                                if message.embeds:
                                    for embed in message.embeds:
                                        if embed.fields:
                                            excluded_fields = ['sol:', 'useful links:', 'buy with bonkbot:']
                                            found_ca = False
                                            
                                            # First pass: Check for CA match
                                            for field in embed.fields:
                                                field_name = field.name.lower() if field.name else ''
                                                if field_name not in excluded_fields:
                                                    ca = field.value.strip() if field.value else ''
                                                    if ca.lower() == self.target_ca.lower():
                                                        found_ca = True
                                                        channel_count += 1
                                                        if embed.description:
                                                            server_data['latest_descriptions'].append(embed.description)
                                                            tx_data = await self.tx.extract_buys_sells(embed.description)
                                                            if tx_data:
                                                                tx_type = tx_data['type']
                                                                sol_amount = tx_data['sol_amount']
                                                                if tx_type == "Buy":
                                                                    channel_buys += sol_amount
                                                                else:
                                                                    channel_sells += sol_amount
                                                        break
                                            
                                            # Second pass: If CA matched, look for trading links
                                            if found_ca:
                                                for field in embed.fields:
                                                    field_name = field.name.lower() if field.name else ''
                                                    if field_name == "useful links:":
                                                        links = field.value.split(" | ")
                                                        for link in links:
                                                            if "Photon](" in link:
                                                                server_data['trading_links']['photon'] = link.split("](")[1].rstrip(")")
                                                            elif "DexScreener](" in link:
                                                                server_data['trading_links']['dex'] = link.split("](")[1].rstrip(")")
                                                            elif "BullX](" in link:
                                                                server_data['trading_links']['bull_x'] = link.split("](")[1].rstrip(")")
                            break  # If successful, break the retry loop
                            
                        except discord.errors.HTTPException as e:
                            retry_count += 1
                            print(f"Rate limit hit for {channel.name}, attempt {retry_count} of {max_retries}")
                            if retry_count < max_retries:
                                await asyncio.sleep(5 * retry_count)
                            else:
                                print(f"Max retries reached for {channel.name}, skipping...")
                                break

                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells

                    server_data['channels'][channel.name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells
                    }
                    
                except Exception as e:
                    print(f"Error counting SWT messages in {channel.name}: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                
                await asyncio.sleep(2)

        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

    async def degen_server_data(self):
        if not self.target_ca:
            return
        
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': []
        }
        
        channel = self.bot.get_channel(self.degen_channel_id)
        if channel:
            try:
                channel_buys = 0.0
                channel_sells = 0.0
                channel_count = 0
                async for message in channel.history(limit=2):
                    if message.embeds:
                        for embed in message.embeds:
                            if embed.fields:
                                # First verify if this embed is for our target CA
                                current_ca = None
                                is_target_tx = False
                                
                                # Check for CA first
                                for field in embed.fields:
                                    if "Token:" in field.value:
                                        try:
                                            current_ca = field.value.split('`')[1].strip()
                                            if current_ca.lower() == self.target_ca.lower():
                                                is_target_tx = True
                                                channel_count += 1
                                                break
                                        except Exception as e:
                                            print(f"Error extracting CA: {e}")
                                            continue
                                
                                # Only process transaction if this is our target CA
                                if is_target_tx:
                                    for field in embed.fields:
                                        if field.value and ("swapped" in field.value.lower() or "transferred" in field.value.lower()):
                                            tx_desc = field.value
                                            if tx_desc:
                                                server_data['latest_descriptions'].append(tx_desc)
                                            
                                            tx_data = await self.tx.extract_degen_buys_sells(tx_desc)
                                            if tx_data:
                                                tx_type = tx_data['type']
                                                sol_amount = tx_data['sol_amount']
                                                
                                                if tx_type == "Buy":
                                                    channel_buys += sol_amount
                                                elif tx_type == "Sell":
                                                    channel_sells += sol_amount

            
                
                server_data['count'] = channel_count
                server_data['buys'] = channel_buys
                server_data['sells'] = channel_sells
                server_data['channels']["Degen"] = {
                    'count': channel_count,
                    'buys': channel_buys,
                    'sells': channel_sells
                }
                                            
            except Exception as e:
                print(f"Error in degen processing: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

        
    async def fresh_server_data(self):
        if not self.target_ca:
            return
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': []
        }
            
        
        for channel_id in self.fresh_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    async for message in channel.history(limit=2):
                        if message.embeds:
                            for embed in message.embeds:
                                if embed.fields:
                                    for field in embed.fields:
                                        if field.name.strip(':').lower() == "token address":
                                            ca = field.value.strip()
                                            if ca.lower() == self.target_ca.lower():
                                                channel_count += 1
                                                if embed.description:
                                                    server_data['latest_descriptions'].append(embed.description)
                                                tx_data = await self.tx.extract_buys_sells(embed.description)
                                                if tx_data:
                                                    tx_type = tx_data['type']
                                                    sol_amount = tx_data['sol_amount']
                                                    if tx_type == "Buy":
                                                        channel_buys += sol_amount
                                                    else:
                                                        channel_sells += sol_amount
                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells

                    server_data['channels'][channel.name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells
                    }
                    

                    
                 
                    
                except Exception as e:
                    print(f"Error counting Fresh messages in {channel.name}: {e}")
                
                await asyncio.sleep(1)
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data


"""
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    
    # Initialize ServerData
    server_data = ServerData(bot)
    
    # Set test CA
    test_ca = ""
    print(f"\nTesting with CA: {test_ca}")
    server_data.target_ca = test_ca
    
    # Test SWT data
    print("\nFetching SWT data...")
    swt_data = await server_data.swt_server_data()
    if swt_data:
        links = swt_data['trading_links']
        print("Trading Links:")
        print(f"Photon: {links['photon']}")
        print(f"DexScreener: {links['dex']}")
        print(f"BullX: {links['bull_x']}")

    
    # Test Degen data
    # Exit after tests
    await bot.close()

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
"""