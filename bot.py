import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
import random
import json
import os
import datetime 

# --- Configuration & Constants ---

TOKEN = '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M' 
NUM_DECKS = 6 
LOG_FILE = 'blackjack_log.json' 
START_GAME_COMMAND = 'startgame'

# Card sets for display and counting (we won't worry about suits for this manual input)
CARD_RANK_KEYS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
CARD_RANKS = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, 
    '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 
    'A': 11 
}
HI_LO_VALUES = {
    '2': 1, '3': 1, '4': 1, '5': 1, '6': 1, 
    '7': 0, '8': 0, '9': 0, 
    '10': -1, 'J': -1, 'Q': -1, 'K': -1, 'A': -1
}

# --- State Management ---
# New structure for manual input and logging
USER_INPUT_STATE = {}
# {user_id: {
#   'step': 'SELECTING_PLAYER_CARD_1', 
#   'player_hand': [], 
#   'dealer_hand': [], 
#   'running_count': 0,
#   'cards_logged': 0 # Total cards logged since start of shoe
# }}

# --- Utility & Strategy Logic ---

def create_card_rank_keyboard():
    """Creates the inline keyboard with card rank buttons."""
    keyboard = []
    # Row 1: A, 2, 3, 4
    keyboard.append([InlineKeyboardButton(r, callback_data=f"rank_{r}") for r in ['A', '2', '3', '4']])
    # Row 2: 5, 6, 7, 8
    keyboard.append([InlineKeyboardButton(r, callback_data=f"rank_{r}") for r in ['5', '6', '7', '8']])
    # Row 3: 9, 10, J, Q, K
    keyboard.append([InlineKeyboardButton(r, callback_data=f"rank_{r}") for r in ['9', '10', 'J', 'Q', 'K']])
    return InlineKeyboardMarkup(keyboard)

def update_count(rank, current_count):
    """Updates the running count based on the selected card rank."""
    return current_count + HI_LO_VALUES.get(rank, 0)

def get_hand_value(hand):
    """Calculates the total value of a hand, handling Aces (11 or 1)."""
    value = 0
    num_aces = 0
    
    for card_rank in hand:
        card_rank_value = CARD_RANKS.get(card_rank, 0)
        value += card_rank_value
        if card_rank == 'A':
            num_aces += 1
            
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def calculate_true_count(running_count, cards_logged):
    """Calculates True Count: Running Count / Remaining Decks."""
    
    # Total cards in the shoe initially
    initial_cards = 52 * NUM_DECKS
    
    # Number of decks remaining
    cards_remaining = initial_cards - cards_logged
    if cards_remaining <= 52: # If less than one deck, it's the last deck
        decks_remaining = 1.0
    else:
        decks_remaining = cards_remaining / 52.0
    
    if decks_remaining < 0.25:
        decks_remaining = 0.25 
        
    true_count = int(running_count / decks_remaining)
    return true_count

# The recommendation function is the same as the previous version
def recommend_action(player_hand, dealer_up_card, true_count):
    """Provides the optimal action based on Basic Strategy and True Count."""
    
    player_value = get_hand_value(player_hand)
    dealer_value = CARD_RANKS.get(dealer_up_card, 10)
    
    if player_value >= 17:
        return "STAND (Always stand on 17+)"
    if player_value <= 8:
        return "HIT (Always hit on 8 or less)"
    
    # Simple Double Down logic on 11
    if player_value == 11:
        if 2 <= dealer_value <= 10 or dealer_up_card == 'A':
             return "DOUBLE DOWN (Optimal vs. Dealer 2-10, A)"
        return "HIT"

    # Player Hand: 12-16 (Stiff hands)
    if 12 <= player_value <= 16:
        if 2 <= dealer_value <= 6:
            # Card Counting Deviation Check for 16 vs 10
            if player_value == 16 and dealer_value == 10 and true_count >= 0: 
                return "STAND (Count favors standing!)"
            return "STAND (Dealer is stiff)"
        
        return "HIT (Dealer is strong)"
        
    return "HIT" # Default catch-all

def log_hand_result(user_id, state, outcome_message):
    """Logs the final details of a completed hand to a JSON file."""
    
    player_value = get_hand_value(state['player_hand'])
    dealer_value = get_hand_value(state['dealer_hand'])
    
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'user_id': user_id,
        'initial_true_count': calculate_true_count(state['running_count'], state['cards_logged']),
        'player_final_hand': state['player_hand'],
        'dealer_final_hand': state['dealer_hand'],
        'player_final_value': player_value,
        'dealer_final_value': dealer_value,
        'game_outcome': outcome_message,
        'final_running_count': state['running_count']
    }
    
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    data.append(log_entry)
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving log file: {e}")

# --- Telegram Handlers ---

async def start_manual_input(update, context):
    """Initiates the manual card input process."""
    user_id = update.effective_user.id
    
    # Initialize the state for this user
    USER_INPUT_STATE[user_id] = {
        'step': 'SELECTING_DEALER_CARD', 
        'player_hand': [], 
        'dealer_hand': [], 
        'running_count': 0,
        'cards_logged': 0
    }
    
    # If this is the first hand, start count from 0
    # If we wanted to persist count between hands, we'd load it here.
    
    await update.message.reply_text(
        "👋 **Manual Hand Logging Started!**\n\n"
        "**Step 1:** Select the Dealer's **UP CARD** (the visible card).",
        reply_markup=create_card_rank_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_card_selection(update, context):
    """Handles card button clicks and moves through the state machine."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data.split('_')
    
    if len(data) != 2 or data[0] != 'rank' or user_id not in USER_INPUT_STATE:
        await query.edit_message_text("Error: Session expired or invalid button. Use **/startgame** to begin.")
        return

    rank = data[1]
    state = USER_INPUT_STATE[user_id]
    
    # Update running count and cards logged for the selected card
    state['running_count'] = update_count(rank, state['running_count'])
    state['cards_logged'] += 1
    
    current_step = state['step']
    next_step_message = ""
    
    # State Machine Logic
    if current_step == 'SELECTING_DEALER_CARD':
        state['dealer_hand'].append(rank)
        state['step'] = 'SELECTING_PLAYER_CARD_1'
        next_step_message = "✅ Dealer Up Card: **{rank}**.\n\n**Step 2:** Select your **FIRST** card."
    
    elif current_step == 'SELECTING_PLAYER_CARD_1':
        state['player_hand'].append(rank)
        state['step'] = 'SELECTING_PLAYER_CARD_2'
        next_step_message = "✅ Player Card 1: **{rank}**.\n\n**Step 3:** Select your **SECOND** card."
        
    elif current_step == 'SELECTING_PLAYER_CARD_2':
        state['player_hand'].append(rank)
        state['step'] = 'ACTION_PHASE'
        # Proceed to the action phase without further card selection
        await display_strategy_action(query, user_id)
        return
    
    elif current_step.startswith('SELECTING_HIT_CARD'):
        # This handles inputting the result of a 'HIT' action
        state['player_hand'].append(rank)
        state['step'] = 'ACTION_PHASE'
        await display_strategy_action(query, user_id)
        return
        
    await query.edit_message_text(
        next_step_message.format(rank=rank),
        reply_markup=create_card_rank_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_strategy_action(update, context):
    """Handles the user clicking an action button (HIT, STAND, SPLIT, DOUBLE)."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data.split('_')[1]
    
    if user_id not in USER_INPUT_STATE or USER_INPUT_STATE[user_id]['step'] != 'ACTION_PHASE':
        await query.edit_message_text("Error: Not in action phase. Use **/startgame** to begin a new hand.")
        return

    state = USER_INPUT_STATE[user_id]
    
    if action == 'hit':
        state['step'] = 'SELECTING_HIT_CARD'
        await query.edit_message_text(
            "🃏 **ACTION: HIT**\n\nSelect the card you received.",
            reply_markup=create_card_rank_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN
        )
    elif action == 'stand':
        # End of hand. Calculate outcome and log.
        await finish_manual_hand(query, user_id, action="STAND")
        
    elif action == 'doubledown':
        state['step'] = 'SELECTING_HIT_CARD' # Player gets one final card
        # After inputting the card, the hand must end (handled in finish_manual_hand)
        await query.edit_message_text(
            "💰 **ACTION: DOUBLE DOWN**\n\nSelect the single card you received.",
            reply_markup=create_card_rank_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN
        )

    elif action == 'split':
        await query.edit_message_text(
            "✂️ **ACTION: SPLIT**\n\nSplitting logic is highly complex and not implemented in this version. Please treat this as a new hand for now or stand.",
            reply_markup=create_strategy_keyboard(state['player_hand'], is_split_hand=True),
            parse_mode=constants.ParseMode.MARKDOWN
        )


async def display_strategy_action(query, user_id):
    """Displays the current hand, count, recommendation, and action buttons."""
    state = USER_INPUT_STATE[user_id]
    player_value = get_hand_value(state['player_hand'])
    
    # 1. Check for Bust/Blackjack immediately
    if player_value > 21:
        await finish_manual_hand(query, user_id, outcome_override="💥 BUST! Your hand value is over 21.")
        return
    if player_value == 21 and len(state['player_hand']) <= 2:
        await finish_manual_hand(query, user_id, outcome_override="🎉 BLACKJACK! This hand is complete.")
        return
        
    # 2. Strategy Calculation
    true_count = calculate_true_count(state['running_count'], state['cards_logged'])
    dealer_up_card = state['dealer_hand'][0]
    recommendation = recommend_action(state['player_hand'], dealer_up_card, true_count)
    
    # 3. Message Formatting
    player_hand_display = ' | '.join(state['player_hand'])
    dealer_up_display = state['dealer_hand'][0]
    
    game_message = (
        "👑 **Blackjack Strategy Coach** 🃏\n"
        "--------------------------------------\n"
        f"Cards Logged: **{state['cards_logged']}**\n"
        f"True Count (Hi-Lo): **{true_count}** (Running: {state['running_count']})\n"
        "--------------------------------------\n"
        f"Dealer Up Card: **{dealer_up_display}**\n"
        f"Your Hand ({player_value}): **{player_hand_display}**\n\n"
        f"💡 **Recommended Action:** `{recommendation}`\n"
    )
    
    await query.edit_message_text(
        game_message,
        reply_markup=create_strategy_keyboard(state['player_hand']),
        parse_mode=constants.ParseMode.MARKDOWN
    )

def create_strategy_keyboard(player_hand, is_split_hand=False):
    """Creates the action keyboard (Hit, Stand, Double Down, Split) dynamically."""
    
    is_initial_deal = len(player_hand) == 2 and not is_split_hand
    can_split = is_initial_deal and (player_hand[0] == player_hand[1])

    keyboard = [
        [InlineKeyboardButton("➕ HIT", callback_data="action_hit"),
         InlineKeyboardButton("🛑 STAND", callback_data="action_stand")]
    ]
    
    # Only allow Double Down and Split on the initial two cards
    if is_initial_deal:
        keyboard.append([InlineKeyboardButton("DOUBLE DOWN 💰", callback_data="action_doubledown")])
    
    if can_split:
         keyboard.append([InlineKeyboardButton("SPLIT ✂️", callback_data="action_split")])

    return InlineKeyboardMarkup(keyboard)

async def finish_manual_hand(query, user_id, action=None, outcome_override=None):
    """Finalizes the hand, calculates results, logs, and resets state."""
    state = USER_INPUT_STATE.pop(user_id) # Game is over, remove state
    
    # Calculate final outcome message
    if outcome_override:
        outcome_message = outcome_override
    else:
        outcome_message = f"Hand completed after action: **{action.upper()}**."
        
    # Log the result
    log_hand_result(user_id, state, outcome_message) 

    # Final Display
    player_hand_display = ' | '.join(state['player_hand'])
    dealer_up_display = state['dealer_hand'][0]
    player_value = get_hand_value(state['player_hand'])
    
    final_message = (
        "♠️ **HAND COMPLETED** ♠️\n"
        "--------------------------------------\n"
        f"**LOGGED RESULT:** {outcome_message}\n"
        "--------------------------------------\n"
        f"Dealer Up Card: **{dealer_up_display}**\n"
        f"Your Final Hand ({player_value}): **{player_hand_display}**\n\n"
        f"Current Running Count: {state['running_count']}\n"
        f"Use **/{START_GAME_COMMAND}** to log the next hand!"
    )

    await query.edit_message_text(
        final_message,
        reply_markup=None,
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    
    application = ApplicationBuilder().token(TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start_manual_input)) 
    application.add_handler(CommandHandler(START_GAME_COMMAND, start_manual_input))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(handle_card_selection, pattern="^rank_"))
    application.add_handler(CallbackQueryHandler(handle_strategy_action, pattern="^action_"))

    print("Manual Blackjack Strategy Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
