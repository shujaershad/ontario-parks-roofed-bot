import os
import datetime
import asyncio
import aiohttp
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Broad accommodation search parameter covering Yurts, Cabins, Cottages, Camp-Cabins & Shelters
EQUIPMENT_CATEGORY_ID = -32768

# Parks in SW, Central, SE Ontario (~250-300km from Cambridge)
PARKS = {
    "Pinery": 71,
    "MacGregor Point": 53,
    "Algonquin": 1,
    "Arrowhead": 6,
    "Awenda": 7,
    "Silent Lake": 82,
    "Sandbanks": 79,
    "Presqu'ile": 74,
    "Earl Rowe": 28,
    "Bass Lake": 9,
    "Sibbald Point": 81,
    "Killarney": 44,
    "Bonnechere": 14,
    "Charleston Lake": 20,
    "Murphys Point": 58,
    "Bronte Creek": 16,
    "Balsam Lake": 8
}

def get_upcoming_weekends(months=5):
    today = datetime.date.today()
    end_date = today + datetime.timedelta(days=30 * months)
    current = today
    
    # Forward to next Friday
    days_until_friday = (4 - current.weekday()) % 7
    current += datetime.timedelta(days=days_until_friday)
    
    weekends = []
    while current <= end_date:
        friday_str = current.strftime("%Y-%m-%d")
        weekends.append(friday_str)
        current += datetime.timedelta(days=7)
        
    return weekends

async def check_park_weekend(session, park_name, park_id, arrival_date):
    params = {
        "mapId": -2147483637,
        "bookingCategoryId": 0,
        "equipmentCategoryId": EQUIPMENT_CATEGORY_ID,
        "subEquipmentCategoryId": 0,
        "cartId": 0,
        "resourceLocationId": park_id,
        "startDate": arrival_date,
        "nights": 2,
        "isLpState": "false"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    try:
        async with session.get("https://reservations.ontarioparks.ca/api/availability/grid", params=params, headers=headers, timeout=12) as resp:
            if resp.status != 200:
                return None
            
            data = await resp.json()
            available_sites = []
            
            if "mapData" in data and "resourceAvailabilities" in data["mapData"]:
                resources = data["mapData"].get("resources", {})
                for site_id, info in data["mapData"]["resourceAvailabilities"].items():
                    # Status 0 represents available
                    if isinstance(info, list) and len(info) >= 2 and info[0] == 0 and info[1] == 0:
                        site_info = resources.get(site_id, {})
                        site_name = site_info.get("name", "Roofed Site")
                        site_type = site_info.get("type", "").lower()
                        
                        # Match roofed accommodations only
                        if any(term in site_type for term in ["yurt", "cabin", "cottage", "camp", "shelter", "roofed"]):
                            available_sites.append(f"{site_name} ({site_type.title()})")
            
            if available_sites:
                return {
                    "park": park_name,
                    "date": arrival_date,
                    "sites": available_sites
                }
    except Exception:
        pass
    return None

def send_discord_notification(matches):
    if not DISCORD_WEBHOOK_URL or not matches:
        return
    
    fields = []
    for match in matches[:10]:
        sites_str = ", ".join(match["sites"][:5])
        if len(match["sites"]) > 5:
            sites_str += f" +{len(match['sites']) - 5} more"
            
        fields.append({
            "name": f"📍 {match['park']} — Weekend of {match['date']}",
            "value": f"**Available:** {sites_str}\n[Book on Ontario Parks](https://reservations.ontarioparks.ca/)",
            "inline": False
        })

    payload = {
        "username": "Ontario Parks Roofed Bot",
        "avatar_url": "https://www.ontarioparks.ca/images/op-logo.png",
        "embeds": [{
            "title": "⛺ Roofed Accommodation Opening Found!",
            "color": 3066993,
            "fields": fields,
            "footer": {"text": "Ontario Parks Roofed Monitor • 5-Month Fri-Sun Check"}
        }]
    }
    
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

async def main():
    weekends = get_upcoming_weekends(months=5)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for park_name, park_id in PARKS.items():
            for friday_str in weekends:
                tasks.append(check_park_weekend(session, park_name, park_id, friday_str))
        
        results = await asyncio.gather(*tasks)
        matches = [r for r in results if r is not None]
        
        if True:
            send_discord_notification(matches)

if __name__ == "__main__":
    asyncio.run(main())
