import os
import discord
from discord.ext import commands
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# ====================== CONFIGURACIÓN ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")

# Canales donde el bot está activo (se reinicia al apagar el bot)
canales_activos = set()

# Cliente de Groq
client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ====================== EVENTOS ======================
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como: {bot.user}")
    print(f"Servidores: {len(bot.guilds)}")
    print("------")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Primero procesamos los comandos
    await bot.process_commands(message)

    # Si el mensaje es un comando, no generamos respuesta de IA
    if message.content.startswith("!"):
        return

    # Solo respondemos si el canal está activo O si mencionan al bot
    canal_activo = message.channel.id in canales_activos
    mencionado = bot.user.mentioned_in(message)

    if not (canal_activo or mencionado):
        return

    # Generar respuesta con IA
    try:
        async with message.channel.typing():
            respuesta = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres un asistente de Discord útil, amable y con un toque de humor. "
                            "Responde siempre en español de forma clara y natural. "
                            "No seas demasiado formal."
                        )
                    },
                    {
                        "role": "user",
                        "content": message.content
                    }
                ],
                max_tokens=900,
                temperature=0.7
            )
            texto = respuesta.choices[0].message.content
            await message.reply(texto, mention_author=False)

    except Exception as e:
        print(f"Error IA: {e}")
        await message.channel.send("❌ Hubo un error al generar la respuesta.")

# ====================== COMANDOS ======================
@bot.command(name="entrar")
@commands.has_permissions(manage_channels=True)
async def entrar(ctx, *, nombre: str = None):
    """Activa el bot en un canal. Ejemplos:
    !entrar
    !entrar #pene-duro
    !entrar pene duro
    """
    if nombre is None:
        canales_activos.add(ctx.channel.id)
        await ctx.send(f"✅ Ahora estoy **activo** en este canal: **#{ctx.channel.name}**")
        return

    # Buscar canal
    canal = None

    # 1. Si mencionaron un canal
    if ctx.message.channel_mentions:
        canal = ctx.message.channel_mentions[0]
    else:
        # 2. Buscar por nombre (flexible)
        busqueda = nombre.lower().replace("#", "").replace("-", " ").strip()
        for ch in ctx.guild.text_channels:
            nombre_ch = ch.name.lower().replace("-", " ")
            if busqueda == nombre_ch or busqueda in nombre_ch:
                canal = ch
                break

    if canal is None:
        await ctx.send("❌ No encontré ese canal. Usa `!entrar #nombre-del-canal`")
        return

    canales_activos.add(canal.id)
    await ctx.send(f"✅ Ahora estoy **activo** en **#{canal.name}**")

@bot.command(name="sacar")
@commands.has_permissions(manage_channels=True)
async def sacar(ctx, *, nombre: str = None):
    """Saca el bot de un canal. Ejemplos:
    !sacar
    !sacar #pene-duro
    !sacar pene duro
    """
    if nombre is None:
        if ctx.channel.id in canales_activos:
            canales_activos.discard(ctx.channel.id)
            await ctx.send(f"✅ Ya **no** estoy activo en este canal.")
        else:
            await ctx.send("ℹ️ No estaba activo aquí.")
        return

    canal = None
    if ctx.message.channel_mentions:
        canal = ctx.message.channel_mentions[0]
    else:
        busqueda = nombre.lower().replace("#", "").replace("-", " ").strip()
        for ch in ctx.guild.text_channels:
            nombre_ch = ch.name.lower().replace("-", " ")
            if busqueda == nombre_ch or busqueda in nombre_ch:
                canal = ch
                break

    if canal is None:
        await ctx.send("❌ No encontré ese canal.")
        return

    if canal.id in canales_activos:
        canales_activos.discard(canal.id)
        await ctx.send(f"✅ Ya **no** estoy activo en **#{canal.name}**")
    else:
        await ctx.send(f"ℹ️ No estaba activo en **#{canal.name}**")

@bot.command(name="canales")
async def canales(ctx):
    """Muestra los canales donde estoy activo"""
    if not canales_activos:
        await ctx.send("📭 No estoy activo en ningún canal.")
        return

    lista = []
    for cid in list(canales_activos):
        canal = bot.get_channel(cid)
        if canal:
            lista.append(f"• #{canal.name}")
        else:
            canales_activos.discard(cid)  # limpiar canales que ya no existen

    if lista:
        await ctx.send("**Canales activos actualmente:**\n" + "\n".join(lista))
    else:
        await ctx.send("📭 No hay canales activos.")

@bot.command(name="ayuda")
async def ayuda(ctx):
    embed = discord.Embed(
        title="🤖 Comandos del Bot de IA",
        description="Controla en qué canales quiero responder",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="!entrar  o  !entrar #canal",
        value="Activa el bot en un canal\nEjemplo: `!entrar #pene-duro`",
        inline=False
    )
    embed.add_field(
        name="!sacar  o  !sacar #canal",
        value="Saca el bot de un canal\nEjemplo: `!sacar #pene-duro`",
        inline=False
    )
    embed.add_field(
        name="!canales",
        value="Muestra la lista de canales activos",
        inline=False
    )
    embed.add_field(
        name="Hablar con la IA",
        value="• Menciona al bot: `@Bot hola`\n• O escribe en un canal activado",
        inline=False
    )
    embed.set_footer(text="Solo usuarios con permiso de Gestionar Canales pueden usar !entrar y !sacar")
    await ctx.send(embed=embed)

# ====================== ERRORES ======================
@entrar.error
@sacar.error
async def permisos_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Necesitas el permiso **Gestionar Canales** para usar este comando.")

# ====================== ARRANQUE ======================
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Falta la variable DISCORD_TOKEN")
    elif not GROQ_API_KEY:
        print("❌ Falta la variable GROQ_API_KEY")
    else:
        bot.run(DISCORD_TOKEN)
