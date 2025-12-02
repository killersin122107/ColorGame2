import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
import random
import json
import os
import asyncio 

# --- Configuration & Constants ---

# Use the token provided in the original request
TOKEN = '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M' 

# Blackjack Game Constants
CARD_SUITS = ['♠️', '♥️', '♦️', '♣️']
CARD_RANKS = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, 
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 
    'A': 11 # Ace starts as 11, logic handles reducing it to 1
}

# --- State Management ---
# Tracks the current game state for each user: 
# {user_id: {'player_hand': [card_str], 'dealer_hand': [card_str], 'game_over': bool}}
GAME_STATE = {}

# --- Game Logic Functions ---

def create_deck():
    """Creates a standard 52-card deck (list of card strings like '♥️A')."""
    deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS.keys():
            deck.append(f"{suit}{rank}")
    random.shuffle(deck)
    return deck

def deal_card(deck):
    """Deals one card from the deck."""
    if not deck:
        # If the deck runs out, create a new one (not strictly standard, but practical for bot)
        deck = create_deck()
    return deck.pop()

def get_hand_value(hand):
    """Calculates the total value of a hand, handling Aces (11 or 1)."""
    value = 0
    num_aces = 0
    
    for card in hand:
        rank = card[1:] # Get the rank part (e.g., 'A', '10')
        card_rank_value = CARD_RANKS.get(rank, 0) # Fallback for two-digit rank '10'
        
        value += card_rank_value
        if rank == 'A':
            num_aces += 1
            
    # Handle Aces: reduce value by 10 for each Ace until value is 21 or less
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def check_game_end(player_value, dealer_value, game_over):
    """Determines the outcome of the game."""
    if not game_over:
        if player_value == 21:
            return "Blackjack! 🎉 Player Wins!", True
        elif player_value > 21:
            return "💥 BUST! Player Loses.", True
        return None, False

    # If game_over is True (meaning the player chose STAND or the dealer finished)
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
    """Formats the hand for display, hiding the dealer's first card if needed."""
    if is_dealer_first_card_hidden and len(hand) > 0:
        # Display: [HIDDEN] [Card 2] (Value: ?)
        visible_cards = hand[1:]
        display = f"**[HIDDEN]** {' '.join(visible_cards)}"
        # Display value only based on the visible card(s)
        value = get_hand_value(visible_cards)
        return display, f"Value: {value} + ?"
    else:
        # Display all cards (Value: X)
        display = ' '.join(hand)
        value = get_hand_value(hand)
        return display, f"Value: **{value}**"

def create_game_keyboard(can_double_down=False):
    """Creates the inline keyboard for game actions."""
    keyboard = [
        [InlineKeyboardButton("➕ HIT", callback_data="action_hit"),
         InlineKeyboardButton("🛑 STAND", callback_data="action_stand")],
        # [InlineKeyboardButton("DOUBLE DOWN", callback_data="action_double")] if can_double_down else []
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Telegram Handlers ---

async def start_game(update, context):
    """Starts a new Blackjack game."""
    user_id = update.effective_user.id
    
    # 1. Initialize Game
    deck = create_deck()
    player_hand = [deal_card(deck), deal_card(deck)]
    dealer_hand = [deal_card(deck), deal_card(deck)]
    
    GAME_STATE[user_id] = {
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'deck': deck, # Store the deck state
        'game_over': False
    }

    player_value = get_hand_value(player_hand)
    
    # 2. Check for initial Blackjack
    message, is_over = check_game_end(player_value, 0, False)
    
    player_display, player_value_display = get_hand_display(player_hand)
    dealer_display, dealer_value_display = get_hand_display(dealer_hand, is_dealer_first_card_hidden=True)
    
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
        game_message += message
    else:
        keyboard = create_game_keyboard()
        game_message += "Choose your action."

    await update.message.reply_text(
        game_message,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_game_action(update, context):
    """Handles HIT and STAND actions."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data.split('_')[1]
    
    if user_id not in GAME_STATE or GAME_STATE[user_id]['game_over']:
        await query.edit_message_text("Game over or session expired. Use **/blackjack** to start a new game.")
        return

    state = GAME_STATE[user_id]
    
    if action == 'hit':
        state['player_hand'].append(deal_card(state['deck']))
        player_value = get_hand_value(state['player_hand'])
        
        # Check for BUST or Blackjack
        message, is_over = check_game_end(player_value, 0, False)
        state['game_over'] = is_over
        
        # If the player is not bust/blackjack, continue the game
        if is_over:
            await finish_game_and_update_message(query, user_id, message)
        else:
            await update_game_message(query, user_id, "Choose your action.")
            
    elif action == 'stand':
        state['game_over'] = True
        
        # Dealer's turn logic
        dealer_value = get_hand_value(state['dealer_hand'])
        while dealer_value < 17:
            state['dealer_hand'].append(deal_card(state['deck']))
            dealer_value = get_hand_value(state['dealer_hand'])

        player_value = get_hand_value(state['player_hand'])
        message, _ = check_game_end(player_value, dealer_value, True)
        
        await finish_game_and_update_message(query, user_id, message)

async def update_game_message(query, user_id, status_message):
    """Updates the game message without ending the game."""
    state = GAME_STATE[user_id]
    
    player_display, player_value_display = get_hand_display(state['player_hand'])
    dealer_display, dealer_value_display = get_hand_display(state['dealer_hand'], is_dealer_first_card_hidden=True)
    
    game_message = (
        "♣️ **Blackjack Game in Progress** ♦️\n\n"
        "--- **Dealer's Hand** ---\n"
        f"{dealer_display}\n{dealer_value_display}\n\n"
        "--- **Your Hand** ---\n"
        f"{player_display}\n{player_value_display}\n\n"
        f"**Status:** {status_message}"
    )
    
    await query.edit_message_text(
        game_message,
        reply_markup=create_game_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def finish_game_and_update_message(query, user_id, outcome_message):
    """Updates the message when the game ends."""
    state = GAME_STATE.pop(user_id) # Remove state now that game is over
    
    player_display, player_value_display = get_hand_display(state['player_hand'])
    dealer_display, dealer_value_display = get_hand_display(state['dealer_hand'], is_dealer_first_card_hidden=False) # Show all cards

    game_message = (
        "♠️ **GAME OVER** ♠️\n\n"
        "--- **Dealer's Final Hand** ---\n"
        f"{dealer_display}\n{dealer_value_display}\n\n"
        "--- **Your Final Hand** ---\n"
        f"{player_display}\n{player_value_display}\n\n"
        f"👑 **RESULT: {outcome_message}**\n\n"
        "Use **/blackjack** to play again!"
    )

    await query.edit_message_text(
        game_message,
        reply_markup=None,
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    # Note: No data.json logic is needed for this pure Blackjack simulation
    
    application = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    # /start is a good default, but /blackjack is clearer
    application.add_handler(CommandHandler("start", start_game)) 
    application.add_handler(CommandHandler("blackjack", start_game))
    
    # Action handler for HIT/STAND buttons
    application.add_handler(CallbackQueryHandler(handle_game_action, pattern="^action_"))

    print("Blackjack Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
