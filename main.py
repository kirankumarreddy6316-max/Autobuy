import discord, json, os, random, requests, asyncio
from discord.ext import commands
from flask import Flask, request
from threading import Thread

# === ENV ===
TOKEN = os.getenv("TOKEN")
NOW_API_KEY = os.getenv("NOW_API_KEY")

# === BOT ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# === CONFIG ===
with open("config.json") as f:
    config = json.load(f)

# === DATA ===
def load_data(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def save_data(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

credits = load_data("data/credits.json")
vouches = load_data("data/vouches.json")

# === MEMORY ===
order_channels = {}
closed_tickets = {}
processed_orders = set()

# === PRODUCTS ===
prices = {
    "Netflix": 3,
    "Spotify": 2.5,
    "Canva": 5,
    "ChatGPT": 9,
    "Auto Advertise 1M": 3,
    "Auto Advertise 1M Reply": 5,
    "Auto Advertise Lifetime": 8,
    "Nitro Gen": 8,
    "Nitro Boosts 1M": 3,
    "Nitro Boosts 3M": 6,
    "Custom Bots": 5,
    "Self Bots": 5,
    "Token Gen": 5,
    "USDT Flasher": 5,
    "Auto Chat": 0.2,
    "Auto Vouch": 0.3,
    "Members": 1,
    "Robux": 5,
    "CC Gen": 5,
    "PayPal Gen": 5
}

# === STOCK ===
def get_stock(product):
    path = f"stock/{product.lower()}.txt"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        lines = f.readlines()
    if not lines:
        return None
    item = lines[0]
    with open(path, "w") as f:
        f.writelines(lines[1:])
    return item.strip()

# === READY ===
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot Ready")

# === PANEL ===
@bot.tree.command(name="panel")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ 〘🤖〙𝗔𝘂𝘁𝗼 𝗕𝘂𝘆",
        description=(
            "Welcome to our automatic purchase system!\n\n"
            "🛒 Select product → Pay → Receive instantly\n\n"
            "⚠️ No refunds after delivery"
        ),
        color=0x5865F2
    )

    view = discord.ui.View()

    async def open_ticket(i):
        category = discord.utils.get(i.guild.categories, name="TICKETS")
        channel = await i.guild.create_text_channel(
            name=f"ticket-{i.user.name}",
            category=category
        )
        await channel.set_permissions(i.user, read_messages=True, send_messages=True)
        await channel.send(i.user.mention)
        await send_buy_panel(channel)
        await i.response.send_message("✅ Ticket created", ephemeral=True)

    btn = discord.ui.Button(label="Open Ticket", style=discord.ButtonStyle.green)
    btn.callback = open_ticket
    view.add_item(btn)

    await interaction.response.send_message(embed=embed, view=view)

# === BUY PANEL ===
async def send_buy_panel(channel):
    embed = discord.Embed(
        title="🛒 Select Product",
        description="Choose what you want to buy",
        color=0x5865F2
    )
    await channel.send(embed=embed, view=ProductView())
    await channel.send(view=TicketControls())

# === PRODUCT VIEW ===
class ProductView(discord.ui.View):
    def __init__(self):
        super().__init__()

        select = discord.ui.Select(
            placeholder="Select product",
            options=[discord.SelectOption(label=p) for p in prices.keys()]
        )

        async def callback(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)

            product = select.values[0]
            price = prices[product]

            invoice = create_invoice(product, price, interaction.user.id)
            order_channels[str(interaction.user.id)] = interaction.channel.id

            embed = discord.Embed(
                title="💳 Payment Created",
                description=(
                    f"**Product:** {product}\n"
                    f"**Price:** ${price}\n\n"
                    f"🔗 [Pay Here]({invoice})\n\n"
                    f"⏳ Status: Waiting..."
                ),
                color=0x5865F2
            )

            await interaction.followup.send(embed=embed)

        select.callback = callback
        self.add_item(select)

# === TICKET CONTROLS ===
class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.send("❌ Cancelled")
        await asyncio.sleep(3)
        await interaction.channel.delete()

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.grey)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        closed_tickets[interaction.user.id] = interaction.channel.name
        await interaction.channel.send("🔒 Closing...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

# === REOPEN ===
@bot.tree.command(name="reopen")
async def reopen(interaction: discord.Interaction):
    name = closed_tickets.get(interaction.user.id)
    if not name:
        return await interaction.response.send_message("No ticket", ephemeral=True)

    category = discord.utils.get(interaction.guild.categories, name="TICKETS")
    channel = await interaction.guild.create_text_channel(name=name, category=category)
    await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
    await send_buy_panel(channel)

    await interaction.response.send_message("Reopened", ephemeral=True)

# === INVOICE ===
def create_invoice(product, price, user_id):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type": "application/json"}

    data = {
        "price_amount": price,
        "price_currency": "usd",
        "pay_currency": "ltc",
        "order_id": str(random.randint(1000,9999)),
        "order_description": f"{product} {user_id}",
        "ipn_callback_url": config["webhook_url"]
    }

    res = requests.post(url, json=data, headers=headers)
    return res.json().get("invoice_url")

# === PAYMENT HANDLER ===
async def handle_payment(data):
    try:
        order_id = data.get("order_id")
        if order_id in processed_orders:
            return
        processed_orders.add(order_id)

        parts = data["order_description"].split()
        user_id = parts[-1]
        product = " ".join(parts[:-1])

        user = await bot.fetch_user(int(user_id))
        channel = bot.get_channel(order_channels.get(user_id))

        if channel:
            await channel.send(f"💰 Payment confirmed for **{product}**")

        item = get_stock(product)

        if not item:
            if channel:
                await channel.send("❌ Out of stock, wait for staff")
            return

        embed = discord.Embed(
            title="✅ Delivery",
            description=f"Here is your **{product}**",
            color=0x00ff99
        )
        embed.add_field(name="Details", value=item)

        try:
            await user.send(embed=embed)
        except:
            if channel:
                await channel.send(embed=embed)

        uid = str(user_id)
        vouches[uid] = vouches.get(uid, 0) + 1
        save_data("data/vouches.json", vouches)

        if channel:
            await channel.send("✅ Delivered! Closing...")
            await asyncio.sleep(10)
            await channel.delete()

    except Exception as e:
        print(e)

# === WEBHOOK ===
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("payment_status") == "finished":
        bot.loop.create_task(handle_payment(data))
    return "OK"

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

Thread(target=run).start()

# === VOUCH ===
@bot.tree.command(name="vouch")
async def vouch(interaction: discord.Interaction, user: discord.Member, amount: int = 1):
    uid = str(user.id)
    vouches[uid] = vouches.get(uid, 0) + amount
    save_data("data/vouches.json", vouches)
    await interaction.response.send_message("Vouch added", ephemeral=True)

@bot.tree.command(name="vouchtop")
async def vouchtop(interaction: discord.Interaction):
    sorted_v = sorted(vouches.items(), key=lambda x: x[1], reverse=True)
    text = "\n".join([f"{i+1}. <@{uid}> — {count}" for i, (uid, count) in enumerate(sorted_v[:10])])
    await interaction.response.send_message(text or "No data")

# === RUN ===
bot.run(TOKEN)
