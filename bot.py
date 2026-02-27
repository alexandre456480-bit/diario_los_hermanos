import discord
from discord.ext import commands
import qrcode
import os
import asyncio
import json
import sys
from dotenv import load_dotenv

load_dotenv()  # carrega o .env
# ================= VERIFICAÇÃO DE BOT DUPLICADO =================

LOCK_FILE = "bot.lock"

# Verificar se já existe uma instância do bot rodando
if os.path.exists(LOCK_FILE):
    print("❌ Erro: Já existe uma instância do bot rodando!")
    print("⚠️  Por favor, feche a outra instância antes de iniciar esta.")
    sys.exit(1)

# Criar arquivo de lock
try:
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
except Exception as e:
    print(f"⚠️  Aviso: Não foi possível criar arquivo de lock: {e}")

def cleanup():
    """Remove o arquivo de lock ao sair"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")

PIX_CODE = "00020126490014BR.GOV.BCB.PIX0127diarioloshermanos@gmail.com52040000530398654045.005802BR5925Alexandre Guimaraes Morat6009SAO PAULO62140510DX2qVguKD86304EBC4"

CANAL_CONFIRMACAO_ID = 1474138137113395403
CANAL_INSCRITOS_ID = 1474098049130434825
STAFF_ROLE_ID = 1455626777295589377
MEMBRO_ROLE_ID = 1474132972503564380

MAX_JOGADORES = 50
ARQUIVO_JSON = "inscricoes.json"
IMAGEM_URL = "https://github.com/alexandre45648-dotcom/morato-apostas/blob/main/3f8ec874-4656-4e35-b673-32cb3bf136bb.png?raw=true"

# ================= SISTEMA JSON =================

def criar_arquivo():
    if not os.path.exists(ARQUIVO_JSON):
        with open(ARQUIVO_JSON, "w") as f:
            json.dump({"inscritos": []}, f, indent=4)

def carregar_dados():
    with open(ARQUIVO_JSON, "r") as f:
        return json.load(f)

def salvar_dados(dados):
    with open(ARQUIVO_JSON, "w") as f:
        json.dump(dados, f, indent=4)

def contar_inscritos():
    return len(carregar_dados()["inscritos"])

def adicionar_inscrito(user_id, nick):
    dados = carregar_dados()

    for jogador in dados["inscritos"]:
        if jogador["nick"].lower() == nick.lower():
            return False

    dados["inscritos"].append({
        "user_id": str(user_id),
        "nick": nick
    })

    salvar_dados(dados)
    return True

def listar_inscritos():
    return [j["nick"] for j in carregar_dados()["inscritos"]]

def remover_inscrito(nick):
    dados = carregar_dados()
    original = len(dados["inscritos"])

    dados["inscritos"] = [
        j for j in dados["inscritos"]
        if j["nick"].lower() != nick.lower()
    ]

    salvar_dados(dados)
    return len(dados["inscritos"]) < original

def limpar_inscritos():
    salvar_dados({"inscritos": []})

criar_arquivo()

# ================= BOT =================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

ticket_count = 0
pago_count = 0
views_registered = False

# ================= TICKET =================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


    @discord.ui.button(label="Abrir Ticket", style=discord.ButtonStyle.green, custom_id="btn_abrir_ticket")
    async def abrir_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        global ticket_count
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")

        if not category:
            category = await guild.create_category("Tickets")

        # Verificar se o usuário já tem um ticket aberto
        tickets_do_usuario = [ch for ch in category.channels if interaction.user in ch.members]
        if tickets_do_usuario:
            await interaction.response.send_message("❌ Você já tem um ticket aberto! Feche-o primeiro.", ephemeral=True)
            return

        ticket_count += 1

        channel_name = f"quero-jogar-{ticket_count:03d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }

        channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎮 DIÁRIO FREE FIRE",
            description="Bem-vindo ao seu ticket de inscrição!",
            color=discord.Color.from_rgb(220, 20, 60)  # Vermelho criado
        )
        embed.add_field(name="💰 PREMIAÇÃO", value="🥇 R$ 20 (1º)\n🥈 R$ 10 (2º)\n🥉 R$ 5 (3º)", inline=True)
        embed.add_field(name="🎯 KILLS", value="R$ 3 por kill", inline=True)
        embed.add_field(name="📊 VAGAS RESTANTES", value=f"{MAX_JOGADORES - contar_inscritos()} disponíveis", inline=False)
        embed.set_footer(text="Clique em 'Fazer o Pix' para efetuar o pagamento")
        embed.set_thumbnail(url=IMAGEM_URL)

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=PagamentoView(channel_name, interaction.user)
        )

        await interaction.response.send_message("✅ Ticket criado!", ephemeral=True)
# ================= FECHAR TICKET =================

class FecharTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Deletar Ticket", style=discord.ButtonStyle.danger, custom_id="btn_fechar_ticket")
    async def fechar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas staff pode deletar.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Deletando ticket...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()

# ================= PAGAMENTO =================

class PagamentoView(discord.ui.View):

    def __init__(self, channel_name, usuario):
        super().__init__(timeout=None)
        self.channel_name = channel_name
        self.usuario = usuario
        self.pix_clicks = 0
        self.confirmado = False

    @discord.ui.button(label="Fazer o Pix", style=discord.ButtonStyle.blurple, custom_id="btn_pix")
    async def fazer_pix(self, interaction: discord.Interaction, button: discord.ui.Button):

        self.pix_clicks += 1
        if self.pix_clicks > 2:
            await interaction.response.send_message("❌ Limite atingido.", ephemeral=True)
            return

        qr = qrcode.make(PIX_CODE)
        qr.save("pix.png")

        file = discord.File("pix.png", filename="pix.png")
        await interaction.channel.send("💰 Após enviar o comprovante confirme o pagamento.", file=file)

        if os.path.exists("pix.png"):
            os.remove("pix.png")

        await interaction.response.defer()

    @discord.ui.button(label="Confirmar Pagamento", style=discord.ButtonStyle.success, custom_id="btn_confirmar_pag")
    async def confirmar_pagamento(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.confirmado:
            await interaction.response.send_message("❌ Este ticket já foi confirmado!", ephemeral=True)
            return

        if contar_inscritos() >= MAX_JOGADORES:
            await interaction.response.send_message("🚫 Vagas esgotadas.", ephemeral=True)
            return

        await interaction.response.send_message("Digite seu nick:", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await bot.wait_for("message", timeout=300, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado. Clique novamente em 'Confirmar Pagamento' para tentar novamente.", ephemeral=True)
            return

        nick = msg.content.strip()

        canal_confirmacao = bot.get_channel(CANAL_CONFIRMACAO_ID)

        if canal_confirmacao:
            view = AprovarView(self.usuario, nick, interaction.channel)

            await canal_confirmacao.send(
                f"📝 **Nova solicitação de inscrição**\n\n"
                f"👤 Jogador: {self.usuario.mention}\n"
                f"🎮 Nick: {nick}\n"
                f"⏳ Status: Aguardando aprovação",
                view=view
            )

            link_canal = f"https://discord.com/channels/{interaction.guild.id}/{CANAL_INSCRITOS_ID}"

            await interaction.followup.send(
                f"📨 Sua inscrição foi enviada!\n\n"
                f"👉 Acompanhe aqui:\n{link_canal}",
                ephemeral=True
            )
            
            # Desabilitar o botão após uso
            self.confirmado = True
            button.disabled = True
            await interaction.message.edit(view=self)

        else:
            await interaction.followup.send("❌ Canal não encontrado.", ephemeral=True)

    @discord.ui.button(label="🔒 Deletar Ticket", style=discord.ButtonStyle.danger, custom_id="btn_del_ticket")
    async def deletar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Permite que o staff delete o ticket"""

        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas staff pode deletar.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 Deletando ticket...", ephemeral=True)
        await asyncio.sleep(1)
        await interaction.channel.delete()

# ================= APROVAÇÃO =================

class AprovarView(discord.ui.View):

    def __init__(self, usuario, nick, ticket_channel):
        super().__init__(timeout=None)
        self.usuario = usuario
        self.nick = nick
        self.ticket_channel = ticket_channel

    @discord.ui.button(label="Aprovar Inscrição", style=discord.ButtonStyle.success, custom_id="btn_aprovar_insc")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):

        global pago_count

        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)
            return

        if contar_inscritos() >= MAX_JOGADORES:
            await interaction.response.send_message("🚫 Limite atingido.", ephemeral=True)
            return

        if not adicionar_inscrito(self.usuario.id, self.nick):
            await interaction.response.send_message("❌ Nick já existe.", ephemeral=True)
            return

        # Incrementar contador de pagos
        pago_count += 1
        novo_nome = f"pago-{pago_count}-{self.nick}"

        # Renomear o ticket
        try:
            await self.ticket_channel.edit(name=novo_nome)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Não foi possível renomear o ticket.", ephemeral=True)

        # Enviar mensagem de confirmação no ticket
        embed = discord.Embed(
            title="✅ INSCRIÇÃO CONFIRMADA!",
            description="🎉 Parabéns! Sua inscrição foi aprovada por um ADM!",
            color=discord.Color.from_rgb(0, 255, 127)  # Verde primavera
        )
        embed.add_field(name="🏆 Você está participando de:", value="Diário Los Hermanos", inline=False)
        embed.add_field(name="⏳ Próximo Passo", value="Aguarde o ID e Senha da sala aqui", inline=False)
        embed.add_field(name="💪 Boa sorte!", value="Mostre seu potencial e ganhe dinheiro! 💰", inline=False)
        embed.set_footer(text="ID e Senha serão enviados em breve")
        embed.set_thumbnail(url=IMAGEM_URL)
        await self.ticket_channel.send(self.usuario.mention, embed=embed)

        # Adicionar cargo de membro ao usuário
        try:
            guild = self.ticket_channel.guild
            membro_role = guild.get_role(MEMBRO_ROLE_ID)
            if membro_role:
                await self.usuario.add_roles(membro_role)
            else:
                await self.ticket_channel.send("⚠️ Cargo de membro não encontrado.", delete_after=5)
        except discord.Forbidden:
            await self.ticket_channel.send("⚠️ Não foi possível adicionar o cargo.", delete_after=5)

        # Enviar mensagem no canal de inscritos
        try:
            canal_inscritos = interaction.client.get_channel(CANAL_INSCRITOS_ID)
            if canal_inscritos:
                guild = self.ticket_channel.guild
                total_inscritos = contar_inscritos()
                
                # Obter lista de membros com o cargo
                membro_role = guild.get_role(MEMBRO_ROLE_ID)
                membros_confirmados = []
                if membro_role:
                    membros_confirmados = [m.mention for m in guild.members if membro_role in m.roles]
                
                membros_text = "\n".join(membros_confirmados) if membros_confirmados else "Nenhum membro confirmado"
                
                embed = discord.Embed(
                    title="✅ Jogador Confirmado",
                    description=f"🎮 Jogador **{self.nick}** foi confirmado no Diário!",
                    color=discord.Color.from_rgb(0, 255, 127)
                )
                embed.add_field(name="📊 Total de inscritos", value=f"**{total_inscritos}/{MAX_JOGADORES}**", inline=False)
                embed.add_field(name="👥 Jogadores confirmados", value=membros_text, inline=False)
                embed.set_thumbnail(url=IMAGEM_URL)
                await canal_inscritos.send(embed=embed)
        except Exception as e:
            pass

        await interaction.response.send_message("✅ Inscrição aprovada!", ephemeral=True)
        

# ================= ADMIN PANEL =================

class AdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


    @discord.ui.button(label="📋 Ver Total", style=discord.ButtonStyle.primary, custom_id="btn_ver_total")
    async def ver_total(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = contar_inscritos()
        await interaction.response.send_message(
            f"📊 Total inscritos: {total}/{MAX_JOGADORES}",
            ephemeral=True
        )

    @discord.ui.button(label="➕ Adicionar Jogador", style=discord.ButtonStyle.success, custom_id="btn_add_jog")
    async def adicionar_jogador(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if contar_inscritos() >= MAX_JOGADORES:
            await interaction.response.send_message("🚫 Vagas esgotadas.", ephemeral=True)
            return

        await interaction.response.send_message("Digite o nick do jogador:", ephemeral=True)

        def check(m):
            return m.author == interaction.user

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado.", ephemeral=True)
            return

        nick = msg.content.strip()

        if not nick:
            await interaction.followup.send("❌ Nick inválido.", ephemeral=True)
            return

        # Adicionar jogador com ID especial do admin
        admin_user_id = f"admin_{interaction.user.id}_{int(__import__('time').time())}"
        
        if adicionar_inscrito(admin_user_id, nick):
            total = contar_inscritos()
            await interaction.followup.send(
                f"✅ Jogador **{nick}** adicionado à fila!\n"
                f"📊 Total: {total}/{MAX_JOGADORES}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(f"❌ Nick **{nick}** já existe na fila.", ephemeral=True)

    @discord.ui.button(label="❌ Remover Jogador", style=discord.ButtonStyle.danger, custom_id="btn_remover_jog")
    async def remover(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("Digite o nick para remover:", ephemeral=True)

        def check(m):
            return m.author == interaction.user

        try:
            msg = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado.", ephemeral=True)
            return

        nick = msg.content.strip()

        if remover_inscrito(nick):
            await interaction.followup.send(f"✅ {nick} removido.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Nick não encontrado.", ephemeral=True)

    @discord.ui.button(label="🧹 Limpar Todos", style=discord.ButtonStyle.secondary, custom_id="btn_limpar_todos")
    async def limpar(self, interaction: discord.Interaction, button: discord.ui.Button):
        limpar_inscritos()
        await interaction.response.send_message("🧹 Lista limpa.", ephemeral=True)

    @discord.ui.button(label="📤 Enviar ID/Senha", style=discord.ButtonStyle.success, custom_id="btn_enviar_cred")
    async def enviar_credenciais(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Envia ID e Senha para todos os tickets com inscrição aprovada"""
        
        await interaction.response.send_message("Digite o ID da sala:", ephemeral=True)

        def check(m):
            return m.author == interaction.user

        try:
            msg_id = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado.", ephemeral=True)
            return

        id_sala = msg_id.content.strip()

        await interaction.followup.send("Digite a Senha da sala:", ephemeral=True)

        try:
            msg_senha = await bot.wait_for("message", timeout=60, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Tempo esgotado.", ephemeral=True)
            return

        senha_sala = msg_senha.content.strip()

        # Encontrar todos os tickets pagos
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")

        if not category:
            await interaction.followup.send("❌ Categoria 'Tickets' não encontrada.", ephemeral=True)
            return

        tickets_pagos = [ch for ch in category.channels if ch.name.startswith("pago-")]

        if not tickets_pagos:
            await interaction.followup.send("❌ Nenhum ticket pago encontrado.", ephemeral=True)
            return

        # Enviar credenciais para cada ticket
        embed = discord.Embed(
            title="🎮 SALA DO DIÁRIO FREE FIRE",
            description="═══════════════════════════════\n🔓 CREDENCIAIS DE ACESSO 🔓\n═══════════════════════════════",
            color=discord.Color.from_rgb(30, 144, 255)  # Azul profundo
        )
        embed.add_field(name="🔑 ID DA SALA", value=f"```{id_sala}```", inline=False)
        embed.add_field(name="🔐 SENHA", value=f"```{senha_sala}```", inline=False)
        embed.add_field(name="⚠️ AVISO IMPORTANTE", value="Não compartilhe essas credenciais com ninguém!", inline=False)
        embed.add_field(name="🎯 BOA SORTE!", value="Mostre suas habilidades e ganhe prêmios! 💰", inline=False)
        embed.set_footer(text="Diário Free Fire - Boa diversão!")
        embed.set_thumbnail(url=IMAGEM_URL)

        for ticket in tickets_pagos:
            try:
                await ticket.send(embed=embed)
            except discord.Forbidden:
                pass

        await interaction.followup.send(
            f"✅ Credenciais enviadas para {len(tickets_pagos)} ticket(s)!",
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ Deletar Tickets Pagos", style=discord.ButtonStyle.danger, custom_id="btn_del_pagos")
    async def deletar_tickets_pagos(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deleta todos os tickets com inscrição confirmada"""

        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")

        if not category:
            await interaction.response.send_message("❌ Categoria 'Tickets' não encontrada.", ephemeral=True)
            return

        tickets_pagos = [ch for ch in category.channels if ch.name.startswith("pago-")]

        if not tickets_pagos:
            await interaction.response.send_message("❌ Nenhum ticket pago encontrado.", ephemeral=True)
            return

        # Deletar todos os tickets
        deletados = 0
        for ticket in tickets_pagos:
            try:
                await ticket.delete()
                deletados += 1
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"🗑️ {deletados} ticket(s) deletado(s) com sucesso!",
            ephemeral=True
        )

    @discord.ui.button(label="👥 Remover Cargo Membros", style=discord.ButtonStyle.secondary, custom_id="btn_rem_cargo")
    async def remover_cargo_membros(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove o cargo de membro de todos os usuários"""

        guild = interaction.guild
        membro_role = guild.get_role(MEMBRO_ROLE_ID)

        if not membro_role:
            await interaction.response.send_message("❌ Cargo de membro não encontrado.", ephemeral=True)
            return

        # Encontrar todos os membros com o cargo
        membros_com_cargo = [m for m in guild.members if membro_role in m.roles]

        if not membros_com_cargo:
            await interaction.response.send_message("❌ Nenhum membro com o cargo foi encontrado.", ephemeral=True)
            return

        # Remover o cargo de cada membro
        removidos = 0
        for membro in membros_com_cargo:
            try:
                await membro.remove_roles(membro_role)
                removidos += 1
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"👥 Cargo removido de {removidos} membro(s)!",
            ephemeral=True
        )

    @discord.ui.button(label="🧹 Limpar Canais", style=discord.ButtonStyle.danger, custom_id="btn_limpar_canais")
    async def limpar_canais(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Limpa todas as mensagens dos canais de confirmação e inscritos"""

        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas staff pode usar.", ephemeral=True)
            return

        await interaction.response.defer()

        canais_ids = [CANAL_CONFIRMACAO_ID, CANAL_INSCRITOS_ID]
        total_deletadas = 0

        for canal_id in canais_ids:
            canal = interaction.client.get_channel(canal_id)
            if not canal:
                await interaction.followup.send(f"⚠️ Canal {canal_id} não encontrado.", ephemeral=True)
                continue

            try:
                # Deletar todas as mensagens do canal
                async for mensagem in canal.history(limit=None):
                    try:
                        await mensagem.delete()
                        total_deletadas += 1
                    except discord.Forbidden:
                        pass
            except Exception as e:
                await interaction.followup.send(f"❌ Erro ao limpar canal {canal_id}: {e}", ephemeral=True)
                continue

        await interaction.followup.send(
            f"🧹 Limpeza concluída! {total_deletadas} mensagem(s) deletada(s).",
            ephemeral=True
        )

    @discord.ui.button(label="📨 Solicitar Histórico/PIX", style=discord.ButtonStyle.blurple, custom_id="btn_solicitar_hist")
    async def solicitar_historico(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Solicita histórico de partida e PIX dos jogadores para pagamento"""

        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Apenas staff pode usar.", ephemeral=True)
            return

        await interaction.response.defer()

        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")

        if not category:
            await interaction.followup.send("❌ Categoria 'Tickets' não encontrada.", ephemeral=True)
            return

        tickets_pagos = [ch for ch in category.channels if ch.name.startswith("pago-")]

        if not tickets_pagos:
            await interaction.followup.send("❌ Nenhum ticket pago encontrado.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 HISTÓRICO E COMPROVANTE NECESSÁRIO",
            description="Por favor, envie os seguintes dados para processamento do pagamento:",
            color=discord.Color.from_rgb(255, 165, 0)  # Laranja
        )
        embed.add_field(name="📊 Histórico de Partida", value="Envie o print do histórico de partida com as kills obtidas", inline=False)
        embed.add_field(name="💳 PIX para Pagamento", value="Envie sua chave PIX para receber o pagamento", inline=False)
        embed.add_field(name="⏰ Prazo", value="Envie essas informações em até 10 minutos para receber seu pagamento", inline=False)
        embed.add_field(name="⚠️ AVISO!!", value="Se não enviar dentro do prazo de 10 minutos, não enviaremos o pagamento.", inline=False)
        embed.set_footer(text="Obrigado por participar!")
        embed.set_thumbnail(url=IMAGEM_URL)

        enviados = 0
        for ticket in tickets_pagos:
            try:
                await ticket.send(embed=embed)
                enviados += 1
            except discord.Forbidden:
                pass

        await interaction.followup.send(
            f"✅ Mensagem enviada para {enviados} ticket(s)!",
            ephemeral=True
        )

# ================= COMANDOS =================

@bot.event
async def on_ready():
    """Registra as views persistentes quando o bot inicia"""
    global views_registered
    
    if not views_registered:
        bot.add_view(TicketView())
        bot.add_view(FecharTicketView())
        bot.add_view(AdminView())
        views_registered = True
        print(f"✅ Bot conectado como {bot.user}")
        print("📎 Views persistentes registradas")
    else:
        print(f"✅ Bot reconectado como {bot.user}")

@bot.command()
async def inscritos(ctx):
    lista = listar_inscritos()
    if not lista:
        await ctx.send("Nenhum inscrito.")
        return
    texto = "\n".join(lista)
    await ctx.send(f"📋 Inscritos:\n{texto}")


@bot.command()
async def painel(ctx):
    embed = discord.Embed(
        title="🔥 DIÁRIO Los Hermanos 🔥",
        description="Participe do diário de Free Fire!",
        color=discord.Color.from_rgb(255, 69, 0)  # Laranja avermelhado
    )
    embed.add_field(name="💰 PREMIAÇÃO", value="🥇 1º Lugar: R$ 20\n🥈 2º Lugar: R$ 10\n🥉 3º Lugar: R$ 5", inline=False)
    embed.add_field(name="🎯 SISTEMA DE KILLS", value="Cada kill = R$ 3,00", inline=False)
    embed.add_field(name="📍 VAGAS DISPONÍVEIS", value=f"**{MAX_JOGADORES - contar_inscritos()}** de {MAX_JOGADORES}", inline=False)
    embed.add_field(name="💳 INSCRIÇÃO", value="R$ 5,00 por jogador", inline=False)
    embed.set_footer(text="Clique no botão abaixo para se inscrever! 👇")
    embed.set_thumbnail(url=IMAGEM_URL)
    
    await ctx.send(embed=embed, view=TicketView())


@bot.command()
async def adm(ctx):

    if STAFF_ROLE_ID not in [r.id for r in ctx.author.roles]:
        await ctx.send("❌ Apenas staff pode usar.")
        return

    embed = discord.Embed(
        title="🛠 Painel Administrativo",
        description="Gerencie inscrições abaixo:",
        color=discord.Color.red()
    )

    await ctx.send(embed=embed, view=AdminView())
# ================= RUN =================

try:
    bot.run(TOKEN)
finally:
    cleanup()
