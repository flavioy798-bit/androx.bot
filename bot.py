import os
import discord
from discord.ext import commands
from openai import AsyncOpenAI
from dotenv import load_dotenv
from duckduckgo_search import DDGS
import asyncio
import urllib.parse

load_dotenv()

# ====================== CONFIGURACIÓN ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL", "openai/gpt-oss-20b")

canales_activos = set()
canales_silenciados = set()

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ====================== FUNCIÓN DE BÚSQUEDA ======================
def buscar_en_internet(pregunta: str) -> str:
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(pregunta, max_results=5))
            if not resultados:
                return "No encontré información relevante."
            
            texto = "Información encontrada en internet:\n\n"
            for i, r in enumerate(resultados, 1):
                texto += f"{i}. {r['title']}\n{r['body']}\nFuente: {r['href']}\n\n"
            return texto
    except Exception as e:
        return f"No pude buscar en internet: {str(e)}"

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

    await bot.process_commands(message)

    if message.content.startswith("!"):
        return

    if message.channel.id in canales_silenciados:
        return

    canal_activo = message.channel.id in canales_activos
    mencionado = bot.user.mentioned_in(message)

    if not (canal_activo or mencionado):
        return

    try:
        async with message.channel.typing():
            busqueda = ""
            palabras_clave = ["quién es", "qué es", "cuándo", "dónde", "cómo", "noticia", "actual", "hoy", "último", "precio", "clima"]
            if any(p in message.content.lower() for p in palabras_clave):
                busqueda = await asyncio.to_thread(buscar_en_internet, message.content)

            system_prompt = (
                "Eres un asistente de Discord útil, amable y con un toque de humor. "
                "Responde siempre en español de forma clara y natural. "
                "Importante: Tú fuiste creado por Señor Fiesta (también conocido como aloa.sd). "
                "Si alguien pregunta quién te creó, quién te programó o de dónde vienes, "
                "responde con orgullo que Señor Fiesta (aloa.sd) te creó. "
                "Nunca digas que te creó otra persona ni una IA.\n\n"
            )

            if busqueda:
                system_prompt += f"Usa esta información actual de internet para responder mejor:\n{busqueda}"

            respuesta = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message.content}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            texto = respuesta.choices[0].message.content
            await message.reply(texto, mention_author=False)

    except Exception as e:
        print(f"Error IA: {e}")
        await message.channel.send("❌ Hubo un error al generar la respuesta.")

# ====================== COMANDOS ======================
@bot.command(name="imagen")
async def imagen(ctx, *, prompt: str = None):
    """Genera una imagen gratis. Uso: !imagen un gato astronauta"""
    if prompt is None:
        await ctx.send("❌ Debes escribir una descripción.\nEjemplo: `!imagen un dragón volando sobre una ciudad`")
        return

    await ctx.send("🎨 Generando imagen, espera un momento...")

    try:
        # Codificar el prompt para la URL
        prompt_encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=1024&height=1024&nologo=true"

        embed = discord.Embed(
            title="🖼️ Imagen generada",
            description=f"**Prompt:** {prompt}",
            color=discord.Color.purple()
        )
        embed.set_image(url=url)
        embed.set_footer(text="Creado por Señor Fiesta (aloa.sd) • Powered by Pollinations")
        
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error al generar la imagen: {str(e)[:100]}")

@bot.command(name="entrar")
@commands.has_permissions(manage_channels=True)
async def entrar(ctx, *, nombre: str = None):
    if nombre is None:
        canales_activos.add(ctx.channel.id)
        canales_silenciados.discard(ctx.channel.id)
        await ctx.send(f"✅ Ahora estoy **activo** en este canal: **#{ctx.channel.name}**")
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

    canales_activos.add(canal.id)
    canales_silenciados.discard(canal.id)
    await ctx.send(f"✅ Ahora estoy **activo** en **#{canal.name}**")

@bot.command(name="sacar")
@commands.has_permissions(manage_channels=True)
async def sacar(ctx, *, nombre: str = None):
    if nombre is None:
        if ctx.channel.id in canales_activos:
            canales_activos.discard(ctx.channel.id)
            await ctx.send("✅ Ya **no** estoy activo en este canal.")
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

@bot.command(name="callate")
@commands.has_permissions(administrator=True)
async def callate(ctx):
    canales_silenciados.add(ctx.channel.id)
    await ctx.send("🔇 Me callo. Solo un administrador puede activarme de nuevo con `!habla`")

@bot.command(name="habla")
@commands.has_permissions(administrator=True)
async def habla(ctx):
    canales_silenciados.discard(ctx.channel.id)
    await ctx.send("🔊 Ya puedo hablar de nuevo en este canal.")

@bot.command(name="canales")
async def canales(ctx):
    if not canales_activos:
        await ctx.send("📭 No estoy activo en ningún canal.")
        return

    lista = []
    for cid in list(canales_activos):
        canal = bot.get_channel(cid)
        if canal:
            estado = "🔇 SILENCIADO" if cid in canales_silenciados else "✅ Activo"
            lista.append(f"• #{canal.name} → {estado}")
        else:
            canales_activos.discard(cid)

    if lista:
        await ctx.send("**Canales:**\n" + "\n".join(lista))
    else:
        await ctx.send("📭 No hay canales activos.")

@bot.command(name="ayuda")
async def ayuda(ctx):
    embed = discord.Embed(
        title="🤖 Comandos del Bot",
        description="Creado por **Señor Fiesta (aloa.sd)**",
        color=discord.Color.blurple()
    )
    embed.add_field(name="!imagen [descripción]", value="🎨 Genera una imagen gratis\nEjemplo: `!imagen un gato con corona`", inline=False)
    embed.add_field(name="!entrar / !sacar", value="Activa o desactiva el bot en un canal", inline=False)
    embed.add_field(name="!callate", value="🔇 Solo **Administradores**. Me calla en este canal", inline=False)
    embed.add_field(name="!habla", value="🔊 Solo **Administradores**. Me deja hablar de nuevo", inline=False)
    embed.add_field(name="!canales", value="Muestra los canales activos", inline=False)
    embed.set_footer(text="Creado con ❤️ por Señor Fiesta (aloa.sd)")
    await ctx.send(embed=embed)

@entrar.error
@sacar.error
@callate.error
@habla.error
async def permisos_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permiso para usar este comando.")

# ====================== ARRANQUE ======================
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Faltan DISCORD_TOKEN o GROQ_API_KEY")
    else:
        bot.run(DISCORD_TOKEN)
