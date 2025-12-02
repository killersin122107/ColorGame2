import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants, Update
from typing import Dict, List, Any
import random
import asyncio

# --- Configuration & Constants ---

# IMPORTANT: REPLACE with your actual bot token if the placeholder is incorrect
TOKEN = '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M'

# Blackjack Game Constants
CARD_SUITS = ['♠️', '♥️', '♦️', '♣️']
CARD_RANKS = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10,
    'A': 11 # Ace starts as 11, logic handles reducing it to 1
}

# --- Game Logic Functions ---

def create_deck() -> List[str]:
    """Creates a standard 52-card deck and shuffles it."""
    deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS.keys():
            deck.append(f"{suit}{rank}")
    random.shuffle(deck)
    return deck

def deal_card(deck: List[str]) -> str:
    """Deals one card from the deck."""
    if not deck:
        deck.extend(create_deck())
        random.shuffle(deck)
    return deck.pop()

def get_hand_value(hand: List[str]) -> int:
    """Calculates the total value of a hand, handling Aces (11 or 1)."""
    value = 0
    num_aces = 0
    
    for card in hand:
        rank = card[1:]
        card_rank_value = CARD_RANKS.get(rank, 0)
        
        value += card_rank_value
        if rank == 'A':
            num_aces += 1
            
    # Handle Aces
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def check_game_outcome(player_value: int, dealer_value: int, game_over: bool) -> tuple[str, bool]:
    """Determines the outcome and if the game is over."""
    
    if not game_over:
        if player_value == 21:
            return "Blackjack! 🎉 Player Wins!", True
        elif player_value > 21:
            return "💥 BUST! Player Loses.", True
        return "Choose your action.", False

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

def get_hand_display(hand: List[str], is_dealer_first_card_hidden: bool = False) -> tuple[str, str]:
    """Formats the hand for display."""
    if is_dealer_first_card_hidden and len(hand) > 0:
        visible_cards = hand[1:]
        display = f"**[HIDDEN]** {' '.join(visible_cards)}"
        visible_value = get_hand_value(visible_cards)
        return display, f"Value: {visible_value} + ?"
    else:
        display = ' '.join(hand)
        value = get_hand_value(hand)
        return display, f"Value: **{value}**"

def create_game_keyboard() -> InlineKeyboardMarkup:
    """Creates the inline keyboard for game actions (HIT/STAND)."""
    keyboard = [
        [InlineKeyboardButton("➕ HIT", callback_data="action_hit"),
         InlineKeyboardButton("🛑 STAND", callback_data="action_stand")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Telegram Handlers ---

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts a new independent Blackjack game for the user."""
    user_data = context.user_data
    
    if user_data.get('blackjack_game', {}).get('game_over') == False:
        await update.message.reply_text("You already have an active game! Please finish it before starting a new one.")
        return
        
    # 1. Initialize Game State
    deck = create_deck()
    player_hand = [deal_card(deck), deal_card(deck)]
    dealer_hand = [deal_card(deck), deal_card(deck)]
    
    user_data['blackjack_game'] = {
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'deck': deck, 
        'game_over': False
    }

    player_value = get_hand_value(player_hand)
    
    # 2. Check for initial Blackjack
    message, is_over = check_game_outcome(player_value, 0, False)
    user_data['blackjack_game']['game_over'] = is_over
    
    # 3. Format Message
    player_display, player_value_display = get_hand_display(player_hand)
    dealer_display, dealer_value_display = get_hand_display(dealer_hand, is_dealer_first_card_hidden=not is_over)
    
    game_message = (
        "♣️ **New Blackjack Game Started!** ♦️\n\n"
        "--- **Dealer's Hand** ---\n"
        f"{dealer_display}\n*{dealer_value_display}*\n\n"
        "--- **Your Hand** ---\n"
        f"{player_display}\n*{player_value_display}*\n\n"
    )
    
    keyboard = None
    if is_over:
        # Game over immediately (Blackjack or bust on initial deal)
        game_message += f"👑 **RESULT:** {message}\n\nUse **/blackjack** to play again!"
    else:
        keyboard = create_game_keyboard()
        game_message += message

    # Store the message ID for editing later
    sent_message = await update.message.reply_text(
        game_message,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    user_data['message_id'] = sent_message.message_id


async def update_game_message_view(update: Update, context: ContextTypes.DEFAULT_TYPE, status_message: str, is_final: bool):
    """Updates the game message view."""
    user_data = context.user_data
    state = user_data.get('blackjack_game', {})
    
    if not state:
        return # Safety check if state was somehow popped early

    player_display, player_value_display = get_hand_display(state['player_hand'])
    dealer_display, dealer_value_display = get_hand_display(state['dealer_hand'], is_dealer_first_card_hidden=not is_final) 

    game_message = (
        f"♠️ **{'GAME OVER' if is_final else 'Blackjack Game in Progress'}** ♥️\n\n"
        "--- **Dealer's Hand** ---\n"
        f"{dealer_display}\n*{dealer_value_display}*\n\n"
        "--- **Your Hand** ---\n"
        f"{player_display}\n*{player_value_display}*\n\n"
    )
    
    if is_final:
        game_message += f"👑 **RESULT: {status_message}**\n\nUse **/blackjack** to play again!"
        reply_markup = None
        # Clean up game state after final display
        user_data.pop('blackjack_game', None)
        user_data.pop('message_id', None)
    else:
        game_message += status_message
        reply_markup = create_game_keyboard()

    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=user_data.get('message_id'),
            text=game_message,
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except telegram.error.BadRequest as e:
        if "Message is not modified" not in str(e):
            print(f"Error editing message: {e}")


async def dealer_turn_and_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles dealer's turn, then resolves and finalizes the game."""
    user_data = context.user_data
    state = user_data['blackjack_game']
    
    # 1. Reveal dealer's hidden card
    # Update view to reveal the hidden card (is_final=False tells it to show all dealer cards)
    await update_game_message_view(update, context, "Player STANDS. Dealer reveals cards...", is_final=False)
    await asyncio.sleep(1.5) 

    dealer_value = get_hand_value(state['dealer_hand'])
    
    # 2. Dealer hits on < 17
    while dealer_value < 17:
        state['dealer_hand'].append(deal_card(state['deck']))
        dealer_value = get_hand_value(state['dealer_hand'])
        
        # Update view for each hit
        await update_game_message_view(update, context, "Dealer hits...", is_final=False)
        await asyncio.sleep(1.5) 
        
    # 3. Final calculation
    player_value = get_hand_value(state['player_hand'])
    final_message, _ = check_game_outcome(player_value, dealer_value, True)

    # 4. Finalize display
    await update_game_message_view(update, context, final_message, is_final=True)


async def handle_game_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles HIT and STAND actions."""
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data
    state = user_data.get('blackjack_game')
    
    # Check if user has an active, non-over game
    if not state or state.get('game_over'):
        await query.edit_message_text("Game over or session expired. Use **/blackjack** to start a new game.")
        return
        
    action = query.data.split('_')[1]
    
    if action == 'hit':
        state['player_hand'].append(deal_card(state['deck']))
        player_value = get_hand_value(state['player_hand'])
        
        # Check for BUST or Blackjack
        message, is_over = check_game_outcome(player_value, 0, False)
        state['game_over'] = is_over
        
        if is_over:
            await update_game_message_view(update, context, message, is_final=True)
        else:
            await update_game_message_view(update, context, message, is_final=False)
            
    elif action == 'stand':
        state['game_over'] = True
        await dealer_turn_and_resolve(update, context)


# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    # The application will store state in context.user_data, making sessions independent.
    application = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_game))
    application.add_handler(CommandHandler("blackjack", start_game))
    
    # Action handler for HIT/STAND buttons
    application.add_handler(CallbackQueryHandler(handle_game_action, pattern="^action_"))

    print("Independent Multi-Session Blackjack Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
