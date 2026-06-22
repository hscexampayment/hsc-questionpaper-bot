import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from database import (
    init_db,
    get_or_create_user,
    get_user,
    add_points,
    set_points,
    register_referral,
    get_referral_count,
    get_referrals,
    get_leaderboard,
    get_all_users,
    get_user_count,
    get_total_referrals,
    search_user,
    get_all_user_ids,
    get_rank,
    next_rank_info,
    RANKS,
    POINTS_PER_REFERRAL,
    POINTS_PER_JOIN,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))

ADMIN_SEARCH, ADMIN_ADJUST_AMOUNT, ADMIN_BROADCAST_MSG = range(3)
admin_state = {}


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def build_referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def rank_progress_bar(points: int) -> str:
    next_name, next_threshold = next_rank_info(points)
    if next_threshold is None:
        return "👑 Maximum rank achieved!"

    prev_threshold = 0
    for threshold, _ in RANKS:
        if points >= threshold:
            prev_threshold = threshold
        else:
            break

    span = next_threshold - prev_threshold
    filled = points - prev_threshold
    pct = filled / span if span > 0 else 1.0
    bars = 10
    filled_bars = round(pct * bars)
    bar = "█" * filled_bars + "░" * (bars - filled_bars)
    return f"[{bar}] {filled}/{span} pts → {next_name}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    db_user = get_or_create_user(user.id, user.username or "", user.first_name or "User")

    referrer_id = None
    if args and args[0].startswith("ref_"):
        try:
            referrer_id = int(args[0][4:])
        except ValueError:
            pass

    awarded_referral = False
    if referrer_id and db_user["points"] == 0 and db_user["referred_by"] is None:
        referrer = get_user(referrer_id)
        if referrer:
            success = register_referral(referrer_id, user.id)
            if success:
                add_points(referrer_id, POINTS_PER_REFERRAL)
                add_points(user.id, POINTS_PER_JOIN)
                awarded_referral = True

    bot_username = (await context.bot.get_me()).username
    ref_link = build_referral_link(bot_username, user.id)

    db_user = get_user(user.id)
    rank = get_rank(db_user["points"])

    welcome = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
        f"🏅 Your Rank: <b>{rank}</b>\n"
        f"⭐ Your Points: <b>{db_user['points']}</b>\n\n"
    )

    if awarded_referral:
        welcome += f"🎉 You joined via a referral and earned <b>{POINTS_PER_JOIN} points</b>!\n\n"

    welcome += (
        "📋 <b>What you can do:</b>\n"
        "/profile — View your full profile\n"
        "/referral — Get your referral link\n"
        "/leaderboard — Top players\n"
        "/ranks — View all ranks\n"
        "/help — Show this menu\n\n"
        f"🔗 <b>Your referral link:</b>\n<code>{ref_link}</code>\n\n"
        f"Earn <b>{POINTS_PER_REFERRAL} pts</b> for each friend you refer!"
    )

    keyboard = [
        [
            InlineKeyboardButton("👤 Profile", callback_data="profile"),
            InlineKeyboardButton("🔗 Referral", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard"),
            InlineKeyboardButton("🎖 Ranks", callback_data="ranks"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_html(welcome, reply_markup=reply_markup)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or "", user.first_name or "User")
    db_user = get_user(user.id)

    rank = get_rank(db_user["points"])
    ref_count = get_referral_count(user.id)
    progress = rank_progress_bar(db_user["points"])
    username_str = f"@{db_user['username']}" if db_user["username"] else "N/A"

    text = (
        f"👤 <b>Profile — {db_user['first_name']}</b>\n"
        f"{'─' * 28}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"🏷 Username: {username_str}\n"
        f"📅 Joined: {db_user['joined_at'][:10]}\n\n"
        f"🏅 Rank: <b>{rank}</b>\n"
        f"⭐ Points: <b>{db_user['points']}</b>\n"
        f"👥 Referrals: <b>{ref_count}</b>\n\n"
        f"📊 <b>Progress:</b>\n{progress}"
    )
    await _reply(update, text)


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or "", user.first_name or "User")

    bot_username = (await context.bot.get_me()).username
    ref_link = build_referral_link(bot_username, user.id)
    ref_count = get_referral_count(user.id)
    referrals = get_referrals(user.id)

    text = (
        f"🔗 <b>Your Referral Stats</b>\n"
        f"{'─' * 28}\n"
        f"👥 Total Referrals: <b>{ref_count}</b>\n"
        f"⭐ Points Earned: <b>{ref_count * POINTS_PER_REFERRAL}</b>\n\n"
        f"📎 <b>Your Link:</b>\n<code>{ref_link}</code>\n\n"
        f"💡 Earn <b>{POINTS_PER_REFERRAL} pts</b> per referral. Your friend gets <b>{POINTS_PER_JOIN} pts</b> too!\n"
    )

    if referrals:
        text += "\n👥 <b>Recent Referrals:</b>\n"
        for r in referrals[:5]:
            uname = f"@{r['username']}" if r["username"] else r["first_name"]
            text += f"  • {uname} — {r['points']} pts ({r['created_at'][:10]})\n"

    await _reply(update, text)


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or "", user.first_name or "User")

    leaders = get_leaderboard(10)
    medals = ["🥇", "🥈", "🥉"]
    text = f"🏆 <b>Leaderboard — Top 10</b>\n{'─' * 28}\n"

    user_rank_pos = None
    for i, row in enumerate(leaders):
        if row["user_id"] == user.id:
            user_rank_pos = i + 1
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = row["first_name"]
        rank = get_rank(row["points"])
        marker = " ← you" if row["user_id"] == user.id else ""
        text += f"{medal} <b>{name}</b> — {row['points']} pts  {rank}{marker}\n"

    if not user_rank_pos:
        db_user = get_user(user.id)
        text += f"\n<i>Your position: unranked — {db_user['points']} pts</i>"

    await _reply(update, text)


async def cmd_ranks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or "", user.first_name or "User")
    db_user = get_user(user.id)
    current_rank = get_rank(db_user["points"])

    text = f"🎖 <b>Rank System</b>\n{'─' * 28}\n"
    for i, (threshold, name) in enumerate(RANKS):
        if i + 1 < len(RANKS):
            next_thresh = RANKS[i + 1][0]
            pts_range = f"{threshold}–{next_thresh - 1} pts"
        else:
            pts_range = f"{threshold}+ pts"
        marker = "  ← you" if name == current_rank else ""
        text += f"{name}: <b>{pts_range}</b>{marker}\n"

    text += (
        f"\n⭐ Your Points: <b>{db_user['points']}</b>\n"
        f"🏅 Your Rank: <b>{current_rank}</b>"
    )
    await _reply(update, text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>Bot Commands</b>\n"
        f"{'─' * 28}\n"
        "/start — Welcome &amp; referral link\n"
        "/profile — Your stats &amp; rank\n"
        "/referral — Referral link &amp; history\n"
        "/leaderboard — Top 10 players\n"
        "/ranks — All ranks &amp; thresholds\n"
        "/help — This message\n\n"
        "💡 <b>How to earn points:</b>\n"
        f"• Refer a friend → +{POINTS_PER_REFERRAL} pts\n"
        f"• Join via referral → +{POINTS_PER_JOIN} pts"
    )
    await _reply(update, text)


# ─── ADMIN PANEL ──────────────────────────────────────────────────────────────

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="adm_stats"),
            InlineKeyboardButton("👥 Users", callback_data="adm_users"),
        ],
        [
            InlineKeyboardButton("🔍 Find User", callback_data="adm_search"),
            InlineKeyboardButton("📢 Broadcast", callback_data="adm_broadcast"),
        ],
    ])


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Access denied.")
        return

    text = (
        "🛠 <b>Admin Panel</b>\n"
        f"{'─' * 28}\n"
        "Choose an action below:"
    )
    await update.message.reply_html(text, reply_markup=admin_main_keyboard())


async def admin_stats(query, context):
    total_users = get_user_count()
    total_refs = get_total_referrals()
    leaders = get_leaderboard(3)

    text = (
        f"📊 <b>Bot Statistics</b>\n"
        f"{'─' * 28}\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"🔗 Total Referrals: <b>{total_refs}</b>\n\n"
        f"🏆 <b>Top 3 Users:</b>\n"
    )
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(leaders):
        uname = f"@{row['username']}" if row["username"] else row["first_name"]
        text += f"{medals[i]} {uname} — {row['points']} pts\n"

    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_btn)


async def admin_users(query, context):
    users = get_all_users(limit=15)
    text = f"👥 <b>Recent Users (last 15)</b>\n{'─' * 28}\n"
    for u in users:
        uname = f"@{u['username']}" if u["username"] else u["first_name"]
        rank = get_rank(u["points"])
        text += f"• <code>{u['user_id']}</code> {uname} — {u['points']} pts {rank}\n"

    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="adm_back")]])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=back_btn)


async def admin_search_prompt(query, context):
    admin_state[query.from_user.id] = {"action": "search"}
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]])
    await query.edit_message_text(
        "🔍 <b>Find User</b>\n\nReply with a user ID or @username:",
        parse_mode="HTML",
        reply_markup=back_btn,
    )


async def admin_broadcast_prompt(query, context):
    admin_state[query.from_user.id] = {"action": "broadcast"}
    back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_back")]])
    await query.edit_message_text(
        "📢 <b>Broadcast Message</b>\n\nType the message to send to ALL users.\n\n⚠️ This cannot be undone.",
        parse_mode="HTML",
        reply_markup=back_btn,
    )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return

    state = admin_state.get(user.id)
    if not state:
        return

    action = state.get("action")
    text = update.message.text.strip()

    if action == "search":
        found = search_user(text)
        if not found:
            await update.message.reply_html("❌ User not found.")
            admin_state.pop(user.id, None)
            return

        ref_count = get_referral_count(found["user_id"])
        rank = get_rank(found["points"])
        uname = f"@{found['username']}" if found["username"] else "N/A"
        msg = (
            f"👤 <b>User Found</b>\n"
            f"{'─' * 28}\n"
            f"🆔 ID: <code>{found['user_id']}</code>\n"
            f"🏷 Username: {uname}\n"
            f"📛 Name: {found['first_name']}\n"
            f"🏅 Rank: {rank}\n"
            f"⭐ Points: <b>{found['points']}</b>\n"
            f"👥 Referrals: <b>{ref_count}</b>\n"
            f"📅 Joined: {found['joined_at'][:10]}\n\n"
            f"To adjust points, reply:\n"
            f"<code>+50 {found['user_id']}</code> (add) or <code>-30 {found['user_id']}</code> (remove)"
        )
        admin_state[user.id] = {"action": "adjust", "target_id": found["user_id"]}
        await update.message.reply_html(msg)

    elif action == "adjust":
        parts = text.split()
        if len(parts) < 1:
            await update.message.reply_text("❌ Format: +50 or -30 (optionally followed by user ID)")
            return

        amount_str = parts[0]
        target_id = state.get("target_id")

        if len(parts) >= 2:
            try:
                target_id = int(parts[1])
            except ValueError:
                pass

        if not target_id:
            await update.message.reply_text("❌ No target user. Use /admin → Find User first.")
            admin_state.pop(user.id, None)
            return

        try:
            amount = int(amount_str)
        except ValueError:
            await update.message.reply_text("❌ Invalid amount. Use e.g. +50 or -20")
            return

        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ User not found.")
            admin_state.pop(user.id, None)
            return

        add_points(target_id, amount)
        updated = get_user(target_id)
        action_word = f"+{amount}" if amount >= 0 else str(amount)
        await update.message.reply_html(
            f"✅ <b>Points Updated</b>\n"
            f"👤 {target['first_name']} (<code>{target_id}</code>)\n"
            f"📝 Change: <b>{action_word} pts</b>\n"
            f"⭐ New Total: <b>{updated['points']} pts</b>\n"
            f"🏅 New Rank: <b>{get_rank(updated['points'])}</b>"
        )
        admin_state.pop(user.id, None)

    elif action == "broadcast":
        user_ids = get_all_user_ids()
        sent = 0
        failed = 0
        broadcast_text = f"📢 <b>Announcement</b>\n\n{text}"
        for uid in user_ids:
            try:
                await context.bot.send_message(uid, broadcast_text, parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1

        await update.message.reply_html(
            f"📢 <b>Broadcast Complete</b>\n"
            f"✅ Sent: <b>{sent}</b>\n"
            f"❌ Failed: <b>{failed}</b>"
        )
        admin_state.pop(user.id, None)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "profile":
        await cmd_profile(update, context)
    elif data == "referral":
        await cmd_referral(update, context)
    elif data == "leaderboard":
        await cmd_leaderboard(update, context)
    elif data == "ranks":
        await cmd_ranks(update, context)
    elif data == "adm_stats":
        await admin_stats(query, context)
    elif data == "adm_users":
        await admin_users(query, context)
    elif data == "adm_search":
        await admin_search_prompt(query, context)
    elif data == "adm_broadcast":
        await admin_broadcast_prompt(query, context)
    elif data == "adm_back":
        admin_state.pop(query.from_user.id, None)
        await query.edit_message_text(
            "🛠 <b>Admin Panel</b>\n─────────────────────────────\nChoose an action below:",
            parse_mode="HTML",
            reply_markup=admin_main_keyboard(),
        )


async def _reply(update: Update, text: str):
    if update.callback_query:
        await update.callback_query.message.reply_html(text)
    else:
        await update.message.reply_html(text)


def main():
    init_db()
    logger.info("Database initialized.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("ranks", cmd_ranks))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
