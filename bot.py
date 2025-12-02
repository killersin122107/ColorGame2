import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, Update
from typing import Dict, List, Any
import random
import asyncio

# --- Configuration & Constants ---

TOKEN = '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M'

# Conversation States
GETTING_LINK = 1

# Blackjack Game Constants
CARD_SUITS = ['♠️', '♥️', '♦️', '♣️']
CARD_RANKS = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10,
    'A': 11
}

# --- State Management (Global Dictionary) ---
GAME_STATE: Dict[int, Dict] = {}
# Stores the message ID to edit (required for ConversationHandler)
MESSAGE_ID_STATE: Dict[int, int] = {} 

# --- Game Logic Functions (Unchanged) ---
# ... (create_deck, deal_card, get_hand_value, check_game_end, get_hand_display, create_game_keyboard)

def create_deck():
    deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS.keys():
            deck.append(f"{suit}{rank}")
    random.shuffle(deck)
    return deck

def deal_card(deck):
    if not deck:
        deck.extend(create_deck())
        random.shuffle(deck)
    return deck.pop()

def get_hand_value(hand):
    value = 0
    num_aces = 0
    for card in hand:
        rank = card[1:]
        card_rank_value = CARD_RANKS.get(rank, 0)
        value += card_rank_value
        if rank == 'A':
            num_aces += 1
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
    return value

def check_game_end(player_value, dealer_value, game_over):
    if not game_over:
        if player_value == 21:
            return "Blackjack! 🎉 Player Wins!", True
        elif player_value > 21:
            return "💥 BUST! Player Loses.", True
        return None, False

    if player_value > 21:
        return "💥 BUST! Player Loses.", True
    elif dealer_value > 21:
        return "✅ Dealer Busts! Player Wins.", True
    elif player_value > dealer_value:
        return "🥳 Player Wins!", True
    elif player_value < dealer_value:
        return "😭 Player Loses.", True
    else:
        return "🤝 Push (Tie).", True

def get_hand_display(hand, is_dealer_first_card_hidden=False):
    if is_dealer_first_card_hidden and len(hand) > 0:
        visible_cards = hand[1:]
        display = f"**[HIDDEN]** {' '.join(visible_cards)}"
        value = get_hand_value(visible_cards)
        return display, f"Value: {value} + ?"
    else:
        display = ' '.join(hand)
        value = get_hand_value(hand)
        return display, f"Value: **{value}**"

def create_game_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ HIT", callback_data="action_hit"),
         InlineKeyboardButton("🛑 STAND", callback_data="action_stand")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Game Start Flow Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initial command to start the game and ask for the link."""
    user_id = update.effective_user.id

    if user_id in GAME_STATE and not GAME_STATE[user_id].get('game_over'):
        await update.message.reply_text("You already have an active game! Please finish it.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("Start Game Now (No Link)", callback_data="start_no_link")]
    ]
    
    # Store the user's message ID so we can edit it later
    sent_message = await update.message.reply_text(
        "👋 Welcome! Please provide a link for game tracking, or press **Start Game Now** to begin immediately without a link.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN
    )
    MESSAGE_ID_STATE[user_id] = sent_message.message_id
    
    # Move to the state where we wait for a link (any message)
    return GETTING_LINK

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user providing a link (any text input)."""
    user_id = update.effective_user.id
    link = update.message.text
    
    # Optional: You can add simple link validation here if needed
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=MESSAGE_ID_STATE.pop(user_id),
        text=f"✅ Link received: `{link}`. Starting game...",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=None
    )
    
    # You can store the link in user_data or context.bot_data if needed globally
    # context.user_data['tracking_link'] = link 
    
    # Immediately proceed to start the game
    return await start_blackjack_game(update, context)


async def start_no_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the button click to start the game without a link."""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Edit the initial message to confirm
    await query.edit_message_text("Starting game without a link...")
    
    # Immediately proceed to start the game
    return await start_blackjack_game(update, context)


async def start_blackjack_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initializes and deals the cards, starting the game (common logic)."""
    user_id = update.effective_user.id
    
    # 1. Initialize Game
    deck = create_deck()
    player_hand = [deal_card(deck), deal_card(deck)]
    dealer_hand = [deal_card(deck), deal_card(deck)]
    
    GAME_STATE[user_id] = {
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'deck': deck,
        'game_over': False
    }

    player_value = get_hand_value(player_hand)
    
    # 2. Check for initial Blackjack
    message, is_over = check_game_end(player_value, 0, False)
    GAME_STATE[user_id]['game_over'] = is_over
    
    player_display, player_value_display = get_hand_display(player_hand)
    dealer_display, dealer_value_display = get_hand_display(dealer_hand, is_dealer_first_card_hidden=not is_over)
    
    # 3. Format Message
    game_message = (
        "♣️ **New Blackjack Game Started!** ♦️\n\n"
        "--- **Dealer's Hand** ---\n"
        f"{dealer_display}\n{dealer_value_display}\n\n"
        "--- **Your Hand** ---\n"
        f"{player_display}\n{player_value_display}\n\n"
    )
    
    keyboard = None
    if is_over:
        game_message += f"👑 **RESULT:** {message}\n\nUse **/start** or **/blackjack** to play again!"
    else:
        keyboard = create_game_keyboard()
        game_message += "Choose your action."

    # Send or edit the message based on how we got here
    if update.callback_query:
        # Came from a button click, so edit the last message
        await update.callback_query.edit_message_text(
             game_message,
             reply_markup=keyboard,
             parse_mode=constants.ParseMode.MARKDOWN
        )
    else:
        # Came from a command (e.g., /blackjack or /start) that wasn't caught by the handler, 
        # or from link input. Reply to the last message.
        await update.message.reply_text(
             game_message,
             reply_markup=keyboard,
             parse_mode=constants.ParseMode.MARKDOWN
        )
        
    # End the conversation flow state
    return ConversationHandler.END


# --- Game Action Handlers (Simplified and integrated) ---

async def update_game_message(query: Update.callback_query, user_id: int, status_message: str, is_final: bool = False):
    """Updates the game message with the current state."""
    state = GAME_STATE.get(user_id)
    if not state:
        await query.edit_message_text("Game session lost. Use /start to restart.", reply_markup=None)
        return
        
    hide_dealer = not is_final and not state.get('game_over', False)

    player_display, player_value_display = get_hand_display(state['player_hand'])
    dealer_display, dealer_value_display = get_hand_display(state['dealer_hand'], is_dealer_first_card_hidden=hide_dealer)
    
    if is_final:
        title = "♠️ **GAME OVER** ♠️"
        status_line = f"👑 **RESULT: {status_message}**\n\nUse **/start** or **/blackjack** to play again!"
        reply_markup = None
        GAME_STATE.pop(user_id, None)
        MESSAGE_ID_STATE.pop(user_id, None)
    else:
        title = "♣️ **Blackjack Game in Progress** ♦️"
        status_line = f"**Status:** {status_message}"
        reply_markup = create_game_keyboard()
        
    game_message = (
        f"{title}\n\n"
        "--- **Dealer's Hand** ---\n"
        f"{dealer_display}\n{dealer_value_display}\n\n"
        "--- **Your Hand** ---\n"
        f"{player_display}\n{player_value_display}\n\n"
        f"{status_line}"
    )
    
    try:
        await query.edit_message_text(
            game_message,
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" not in str(e):
            print(f"Error editing message: {e}")


async def dealer_turn_and_resolve(query: Update.callback_query, user_id: int):
    """Handles dealer's turn, then resolves and finalizes the game."""
    state = GAME_STATE[user_id]
    
    await update_game_message(query, user_id, "Player STANDS. Dealer reveals cards...", is_final=False)
    await asyncio.sleep(1.5)

    dealer_value = get_hand_value(state['dealer_hand'])
    
    while dealer_value < 17:
        state['dealer_hand'].append(deal_card(state['deck']))
        dealer_value = get_hand_value(state['dealer_hand'])
        pass # Skip intermediate updates for simplicity

    player_value = get_hand_value(state['player_hand'])
    final_message, _ = check_game_end(player_value, dealer_value, True)

    await update_game_message(query, user_id, final_message, is_final=True)


async def handle_game_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles HIT and STAND actions."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data.split('_')[1]
    
    if user_id not in GAME_STATE or GAME_STATE[user_id]['game_over']:
        try:
             await query.edit_message_text("Game over or session expired. Use **/start** or **/blackjack** to start a new game.", reply_markup=None)
        except telegram.error.BadRequest:
             pass 
        return

    state = GAME_STATE[user_id]
    
    if action == 'hit':
        state['player_hand'].append(deal_card(state['deck']))
        player_value = get_hand_value(state['player_hand'])
        
        message, is_over = check_game_end(player_value, 0, False)
        state['game_over'] = is_over
        
        if is_over:
            await update_game_message(query, user_id, message, is_final=True)
        else:
            await update_game_message(query, user_id, "Choose your action.", is_final=False)
            
    elif action == 'stand':
        state['game_over'] = True
        await dealer_turn_and_resolve(query, user_id)

async def fallback_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the game immediately if /blackjack is used."""
    # This handler is outside the ConversationHandler, allowing /blackjack to always bypass the link prompt.
    await start_blackjack_game(update, context)
    return ConversationHandler.END

# --- Main Bot Execution ---

def main():
    application = ApplicationBuilder().token(TOKEN).build()
    
    # 1. Conversation Handler for /start (Optional Link Input)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GETTING_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link),
                CallbackQueryHandler(start_no_link_callback, pattern="^start_no_link$"),
                # Fallback: If they use /blackjack or another command, cancel this conversation
                CommandHandler("blackjack", fallback_start_game), 
                CommandHandler("cancel", fallback_start_game) 
            ]
        },
        fallbacks=[
            CommandHandler("start", start) # Restart if the conversation fails
        ],
        allow_reentry=True
    )
    application.add_handler(conv_handler)
    
    # 2. Direct Handler for /blackjack (Always starts the game immediately)
    application.add_handler(CommandHandler("blackjack", fallback_start_game))
    
    # 3. Action Handler for game buttons
    application.add_handler(CallbackQueryHandler(handle_game_action, pattern="^action_"))

    print("Blackjack Bot is running... Press Ctrl+C to stop.")
    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    main()
