import os
import discord
from discord.ext import commands
from openai import AsyncOpenAI
from dotenv import load_dotenv
from duckduckgo_search import DDGS
import asyncio
import urllib.parse
from collections import defaultdict, deque

load_dotenv()

# ====================== CONFIGURACIÓN ======================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("MODEL", "openai/gpt-oss-20b")

CREATOR_ID = 1247581878148399155

canales_activos = set()
canales_silenciados = set()

memoria = defaultdict(lambda: deque(maxlen=10))

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ====================== FUNCIONES ======================
def buscar_en_internet(pregunta: str) -> str:
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(pregunta, max_results=6))
            if not resultados:
                return "No encontré información reciente sobre eso."
            
            texto = "=== INFORMACIÓN ACTUAL DE INTERNET (2026) ===\n\n"
            for i, r in enumerate(resultados, 1):
                texto += f"{i}. {r.get('title', 'Sin título')}\n{r.get('body', '')}\nFuente: {r.get('href', '')}\n\n"
            return texto
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return "No pude obtener información actual en este momento."

def detectar_pedido_imagen(texto: str) -> str | None:
    texto = texto.lower()
    triggers = [
        "hazme una imagen", "genera una imagen", "crea una imagen",
        "haz una imagen", "quiero una imagen", "dibuja", "genera una foto",
        "hazme un dibujo", "crea una foto", "imagen de", "foto de"
    ]
    for t in triggers:
        if t in texto:
            idx = texto.find(t) + len(t)
            prompt = texto[idx:].strip(" :,-")
            return prompt if prompt else None
    return None

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

    # Detección de imagen
    prompt_imagen = detectar_pedido_imagen(message.content)
    if prompt_imagen:
        await generar_imagen(message.channel, prompt_imagen)
        return

    es_creador = message.author.id == CREATOR_ID
    nombre_usuario = message.author.display_name

    # Guardar en memoria
    memoria[message.channel.id].append({
        "role": "user",
        "content": f"{nombre_usuario}: {message.content}"
    })

    try:
        async with message.channel.typing():

            contenido_lower = message.content.lower()

            # Forzar búsqueda si habla de años recientes o pide info actual
            forzar_busqueda = any(p in contenido_lower for p in [
                "2025", "2026", "2024", "este año", "el año pasado",
                "qué pasó", "que paso", "noticias", "actual", "hoy",
                "hace poco", "reciente", "últimamente", "ahora"
            ])

            busqueda = ""
            if forzar_busqueda or any(p in contenido_lower for p in ["quién", "qué es", "cuándo", "dónde", "cómo", "precio", "clima"]):
                busqueda = await asyncio.to_thread(buscar_en_internet, message.content)

            # System prompt fuerte
            if es_creador:
                system_prompt = (
                    "Eres un asistente de Discord inteligente, amable y con humor.\n\n"
                    "FECHA ACTUAL: Septiembre de 2026.\n"
                    "Nunca digas que tu conocimiento termina en 2023 o 2024. "
                    "Estamos en 2026. Si no sabes algo reciente, usa la información de internet que te proporciono.\n\n"
                    "IMPORTANTE: Estás hablando DIRECTAMENTE con tu creador, Señor Fiesta (aloa.sd). "
                    "Su ID es 1247581878148399155. Trátalo con respeto y cercanía.\n\n"
                    "REGLA DE ORO: Siempre usa el historial de la conversación. "
                    "Si el usuario responde con una palabra corta, es continuación de lo anterior."
                )
            else:
                system_prompt = (
                    "Eres un asistente de Discord inteligente, amable y con humor.\n\n"
                    "FECHA ACTUAL: Septiembre de 2026.\n"
                    "Nunca digas que tu conocimiento termina en 2023 o 2024. "
                    "Estamos en 2026. Si no sabes algo reciente, usa la información de internet que te proporciono.\n\n"
                    "Fuiste creado por Señor Fiesta (aloa.sd). "
                    "Si preguntan quién te creó, di con orgullo que fue Señor Fiesta (aloa.sd).\n\n"
                    "REGLA DE ORO: Siempre usa el historial de la conversación. "
                    "Si el usuario responde con una palabra corta, es continuación de lo anterior."
                )

            if busqueda:
                system_prompt += f"\n\n{busqueda}"

            # Construir mensajes
            messages = [{"role": "system", "content": system_prompt}]
            for msg in list(memoria[message.channel.id]):
                messages.append(msg)

            respuesta = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=1100,
                temperature=0.65
            )
            texto = respuesta.choices[0].message.content

            # Guardar respuesta
            memoria[message.channel.id].append({
                "role": "assistant",
                "content": texto
            })

            await message.reply(texto, mention_author=False)

    except Exception as e:
        print(f"Error IA: {e}")
        await message.channel.send("❌ Hubo un error al generar la respuesta. Intenta de nuevo.")

# ====================== GENERACIÓN DE IMÁGENES ======================
async def generar_imagen(channel, prompt: str, cantidad: int = 1, estilo: str = None, tamaño: str = "cuadrada"):
    await channel.send("🎨 Generando imagen(es)...")

    if estilo:
        estilos = {
            "anime": "anime style, vibrant colors, detailed",
            "realista": "photorealistic, highly detailed, 8k",
            "cyberpunk": "cyberpunk style, neon lights, futuristic",
            "fantasia": "fantasy art, magical, epic",
            "minimalista": "minimalist style, clean, simple",
            "oscuro": "dark atmosphere, dramatic lighting",
            "cartoon": "cartoon style, colorful, fun"
        }
        prompt = f"{prompt}, {estilos.get(estilo.lower(), estilo)}"

    tamanos = {
        "cuadrada": (1024, 1024),
        "horizontal": (1280, 720),
        "vertical": (720, 1280),
        "grande": (1280, 1280)
    }
    width, height = tamanos.get(tamaño.lower(), (1024, 1024))
    cantidad = max(1, min(cantidad, 4))

    try:
        for i in range(cantidad):
            prompt_encoded = urllib.parse.quote(prompt)
            seed = abs(hash(prompt + str(i))) % 999999
            url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width={width}&height={height}&nologo=true&seed={seed}&enhance=true"

            embed = discord.Embed(
                title=f"🖼️ Imagen generada {i+1}/{cantidad}",
                description=f"**Prompt:** {prompt}",
                color=discord.Color.purple()
            )
            embed.set_image(url=url)
            embed.set_footer(text="Creado por Señor Fiesta (aloa.sd)")
            await channel.send(embed=embed)
    except Exception as e:
        await channel.send(f"❌ Error al generar la imagen: {str(e)[:120]}")

@bot.command(name="imagen")
async def imagen(ctx, *, args: str = None):
    if not args:
        await ctx.send(
            "❌ Ejemplos:\n"
            "`!imagen un gato astronauta`\n"
            "`!imagen un dragón --estilo anime --tamaño horizontal`\n"
            "`!imagen un castillo --cantidad 2 --estilo fantasia`"
        )
        return

    prompt = args
    estilo = None
    tamaño = "cuadrada"
    cantidad = 1

    if "--estilo" in args:
        partes = args.split("--estilo")
        prompt = partes[0].strip()
        resto = partes[1].strip().split()
        estilo = resto[0] if resto else None

    if "--tamaño" in args or "--tamano" in args:
        key = "--tamaño" if "--tamaño" in args else "--tamano"
        partes = args.split(key)
        resto = partes[1].strip().split()
        tamaño = resto[0] if resto else "cuadrada"

    if "--cantidad" in args:
        partes = args.split("--cantidad")
        resto = partes[1].strip().split()
        try:
            cantidad = int(resto[0])
        except:
            cantidad = 1

    await generar_imagen(ctx.channel, prompt, cantidad, estilo, tamaño)

# ====================== COMANDOS DE CONTROL ======================
@bot.command(name="entrar")
@commands.has_permissions(manage_channels=True)
async def entrar(ctx, *, nombre: str = None):
    if nombre is None:
        canales_activos.add(ctx.channel.id)
        canales_silenciados.discard(ctx.channel.id)
        await ctx.send(f"✅ Ahora estoy **activo** en **#{ctx.channel.name}**")
        return

    canal = None
    if ctx.message.channel_mentions:
        canal = ctx.message.channel_mentions[0]
    else:
        busqueda = nombre.lower().replace("#", "").replace("-", " ").strip()
        for ch in ctx.guild.text_channels:
            if busqueda in ch.name.lower().replace("-", " "):
                canal = ch
                break

    if not canal:
        await ctx.send("❌ No encontré ese canal.")
        return

    canales_activos.add(canal.id)
    canales_silenciados.discard(canal.id)
    await ctx.send(f"✅ Ahora estoy **activo** en **#{canal.name}**")

@bot.command(name="sacar")
@commands.has_permissions(manage_channels=True)
async def sacar(ctx, *, nombre: str = None):
    if nombre is None:
        canales_activos.discard(ctx.channel.id)
        await ctx.send("✅ Ya no estoy activo en este canal.")
        return

    canal = None
    if ctx.message.channel_mentions:
        canal = ctx.message.channel_mentions[0]
    else:
        busqueda = nombre.lower().replace("#", "").replace("-", " ").strip()
        for ch in ctx.guild.text_channels:
            if busqueda in ch.name.lower().replace("-", " "):
                canal = ch
                break

    if not canal:
        await ctx.send("❌ No encontré ese canal.")
        return

    canales_activos.discard(canal.id)
    await ctx.send(f"✅ Ya no estoy activo en **#{canal.name}**")

@bot.command(name="callate")
@commands.has_permissions(administrator=True)
async def callate(ctx):
    canales_silenciados.add(ctx.channel.id)
    await ctx.send("🔇 Me callo. Usa `!habla` para activarme de nuevo.")

@bot.command(name="habla")
@commands.has_permissions(administrator=True)
async def habla(ctx):
    canales_silenciados.discard(ctx.channel.id)
    await ctx.send("🔊 Ya puedo hablar de nuevo.")

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
    await ctx.send("**Canales:**\n" + "\n".join(lista))

@bot.command(name="ayuda")
async def ayuda(ctx):
    embed = discord.Embed(
        title="🤖 Comandos del Bot",
        description="Creado por **Señor Fiesta (aloa.sd)**",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="!imagen [descripción]",
        value=(
            "🎨 Genera imágenes\n"
            "`--estilo anime/realista/cyberpunk/fantasia`\n"
            "`--tamaño cuadrada/horizontal/vertical/grande`\n"
            "`--cantidad 1-4`"
        ),
        inline=False
    )
    embed.add_field(name="!entrar / !sacar", value="Activa o desactiva el bot", inline=False)
    embed.add_field(name="!callate / !habla", value="Solo Administradores", inline=False)
    embed.add_field(name="!canales", value="Estado de los canales", inline=False)
    embed.set_footer(text="Creado con ❤️ por Señor Fiesta (aloa.sd) • Septiembre 2026")
    await ctx.send(embed=embed)

@entrar.error
@sacar.error
@callate.error
@habla.error
async def error_permisos(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ No tienes permiso para usar este comando.")

# ====================== ARRANQUE ======================
if __name__ == "__main__":
    if not DISCORD_TOKEN or not GROQ_API_KEY:
        print("❌ Faltan DISCORD_TOKEN o GROQ_API_KEY")
    else:
        bot.run(DISCORD_TOKEN)
