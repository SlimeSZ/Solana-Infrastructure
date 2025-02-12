import asyncio
import aiohttp
import requests
import re
from datetime import datetime

class TX_ANALYZER:
    def __init__(self):
        pass

    async def extract_buys_sells(self, description):
        if not description:
            print(f"Critical Error: tx description not found... ")
            return
        try:
            description_lower = description.lower()

            parts = description_lower.split("swapped")[1].strip().split(" for ")
            if len(parts) != 2:
                print(f"Error formatting description")
                return None
            
            from_amount, to_amount = parts

            if "sol" in from_amount.lower():
                tx_type = "Buy"
                try:
                    sol_amount = float(re.findall(r"[\d,.]+", from_amount)[0].replace(",", ""))
                except (IndexError, ValueError) as e:
                    print(f"Error parsing buy amounts: {str(e)}")
                    return None
                
            else:
                tx_type = "Sell"
                try:
                    sol_amount = float(re.findall(r"[\d,.]+", to_amount)[0].replace(",", ""))
                except (IndexError, ValueError) as e:
                    print(f"Error parsing amounts: {e}")
                    return None
            
            return {
                "type": tx_type,
                "sol_amount": sol_amount,
                "raw_description": description
            }
        
        except Exception as e:
            return None
        
    async def extract_degen_buys_sells(self, description):
        if not description:
            return None
        
        try:
            # First clean up the description
            clean_desc = description.replace('*', '').strip()
            
            # Determine transaction type
            is_buy = "🟢" in description
            is_sell = "🔴" in description
            
            if not (is_buy or is_sell):
                return None
            
            # Extract SOL amount using regex pattern that matches numbers before or after "SOL"
            sol_pattern = r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:SOL|for\s+\*\*(\d+(?:,\d+)?(?:\.\d+)?)\s*SOL)'
            matches = re.findall(sol_pattern, clean_desc)
            
            if not matches:
                return None
                
            # Get the SOL amount - take first non-empty match
            sol_str = next((m for m in matches[0] if m), None)
            if not sol_str:
                return None
                
            # Convert to float, handling commas
            sol_amount = float(sol_str.replace(',', ''))
            
            return {
                "type": "Buy" if is_buy else "Sell",
                "sol_amount": sol_amount,
                "raw_description": description
            }
            
        except Exception as e:
            print(f"Error processing degen transaction: {str(e)}")
            print(f"Problem description: {description}")
        return None
                        