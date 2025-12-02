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
MAX_PLAYERS = 3 # Dealer + 3 players

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
        # Re-create and shuffle if necessary
        deck.extend(create_deck())
        random.shuffle(deck)
    return deck.pop()

def get_hand_value(hand: List[str]) -> int:
    """Calculates the total value of a hand, handling Aces (11 or 1)."""
    value = 0
    num_aces = 0
    
    for card in hand:
        # Safely extract rank (handles multi-char ranks like '10')
        rank = card[1:] 
        card_rank_value = CARD_RANKS.get(rank, 0)
        
        value += card_rank_value
        if rank == 'A':
            num_aces += 1
            
    # Handle Aces: reduce value by 10 for each Ace until value is 21 or less
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def check_outcome(player_value: int, dealer_value: int, player_status: str) -> str:
    """Determines the outcome for a single player against the dealer."""
    
    if player_status == 'blackjack':
        return "Blackjack! 🎉 Player Wins!"
        
    if player_value > 21:
        return "💥 BUST! Player Loses."
    
    # If the player is not bust/blackjack, check dealer
    if dealer_value > 21:
        return "✅ Dealer Busts! Player Wins."
    
    if player_status != 'stand' and player_status != 'blackjack':
        # Should only run if a player is in the middle of a round (shouldn't be called here)
        return "Still playing..." 

    # Final comparison (Player stood or had Blackjack)
    if player_value > dealer_value:
        return "🥳 Player Wins!"
    elif player_value < dealer_value:
        return "😭 Player Loses."
    else:
        return "🤝 Push (Tie)."

def get_hand_display(hand: List[str], is_dealer_first_card_hidden: bool = False) -> tuple[str, str]:
    """Formats the hand for display."""
    if is_dealer_first_card_hidden and len(hand) > 0:
        # Display: [HIDDEN] [Card 2] (Value: ?)
        visible_cards = hand[1:]
        display = f"**[HIDDEN]** {' '.join(visible_cards)}"
        visible_value = get_hand_value(visible_cards)
        return display, f"Value: {visible_value} + ?"
    else:
        # Display all cards (Value: X)
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

# --- Telegram Helper Functions ---

async def update_game_message(context: ContextTypes.DEFAULT_TYPE, status_message: str, reply_markup: InlineKeyboardMarkup = None):
    """Updates the main game message in the chat."""
    chat_data = context.chat_data
    state = chat_data['blackjack_game']

    dealer_display, dealer_value_display = get_hand_display(
        state['dealer_hand'], 
        is_dealer_first_card_hidden=(state['stage'] not in ['finished', 'dealer_turn'])
    )
    
    msg = "♠️ **GROUP BLACKJACK** ♥️\n\n"
    msg += "--- **Dealer** ---\n"
    msg += f"{dealer_display}\n*{dealer_value_display}*\n\n"
    
    msg += "--- **Players** ---\n"
    
    player_ids = list(state['players'].keys())
    
    for user_id in player_ids:
        player = state['players'][user_id]
        
        player_display, player_value_display = get_hand_display(player['hand'])
        player_value = get_hand_value(player['hand'])
        
        indicator = "👉" if user_id == state['active_player'] else " "
        
        # Determine Status Text
        status_text = player['status'].upper()
        if player['status'] == 'playing' and state['active_player'] == user_id:
            status_text = "YOUR TURN"
        elif player['status'] == 'playing':
            status_text = "Waiting"
        
        # Player Display
        msg += f"{indicator} **{player['name']}** ({player_value}): *{status_text}*\n"
        msg += f"   Cards: {player_display}\n\n"
        
    msg += f"**STATUS:** {status_message}"

    try:
        if chat_data.get('message_id'):
            await context.bot.edit_message_text(
                chat_id=context.effective_chat.id, 
                message_id=chat_data['message_id'],
                text=msg,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.MARKDOWN
            )
    except telegram.error.BadRequest as e:
        # Ignore "Message is not modified" error which happens when hitting/standing results in the same display
        if "Message is not modified" not in str(e):
            print(f"Error editing message: {e}")
        
async def finalize_game_message(context: ContextTypes.DEFAULT_TYPE):
    """Calculates all results and shows the final game state."""
    chat_data = context.chat_data
    state = chat_data['blackjack_game']
    
    dealer_value = get_hand_value(state['dealer_hand'])
    
    # Generate final result summary
    final_results = "--- **FINAL RESULTS** ---\n"
    for user_id, player in state['players'].items():
        player_value = get_hand_value(player['hand'])
        
        # Use the combined check_outcome function for the final verdict
        outcome = check_outcome(player_value, dealer_value, player['status'])
        
        final_results += f"**{player['name']}** ({player_value}) vs. Dealer ({dealer_value}): {outcome}\n"
        
    final_results += "\nUse **/startgame** to play again!"

    # Force game stage to finished for display purposes
    state['stage'] = 'finished' 

    # Generate final display
    dealer_display, dealer_value_display = get_hand_display(state['dealer_hand']) # Show all dealer cards
    
    final_msg = "♠️ **GAME OVER** ♠️\n\n"
    final_msg += "--- **Dealer's Final Hand** ---\n"
    final_msg += f"{dealer_display}\n*{dealer_value_display}*\n\n"
    final_msg += "--- **Players** ---\n"
    
    for player in state['players'].values():
        player_display, player_value_display = get_hand_display(player['hand'])
        player_value = get_hand_value(player['hand'])
        final_msg += f"**{player['name']}** ({player_value}):\n"
        final_msg += f"   Cards: {player_display}\n\n"
        
    final_msg += final_results
    
    # Clean up state
    message_id = chat_data.get('message_id')
    chat_data.pop('blackjack_game')
    if 'message_id' in chat_data:
        chat_data.pop('message_id')
    
    # Edit the final message
    await context.bot.edit_message_text(
        chat_id=context.effective_chat.id, 
        message_id=message_id,
        text=final_msg,
        reply_markup=None,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def move_to_next_player(context: ContextTypes.DEFAULT_TYPE, status_message: str):
    """Finds the next 'playing' user or starts the dealer's turn."""
    chat_data = context.chat_data
    state = chat_data['blackjack_game']
    player_ids = list(state['players'].keys())
    
    try:
        current_index = player_ids.index(state['active_player'])
    except ValueError:
        current_index = -1 
        
    next_active_player = None
    
    # Find the next player who is still 'playing'
    for i in range(current_index + 1, len(player_ids)):
        next_id = player_ids[i]
        if state['players'][next_id]['status'] == 'playing':
            next_active_player = next_id
            break
            
    if next_active_player:
        state['active_player'] = next_active_player
        await update_game_message(context, status_message, create_game_keyboard())
    else:
        # All players have acted. Start Dealer's turn.
        state['active_player'] = None
        await dealer_turn(context, status_message)

async def dealer_turn(context: ContextTypes.DEFAULT_TYPE, initial_status_message: str):
    """Executes the dealer's drawing phase and resolves the game."""
    state = context.chat_data['blackjack_game']
    state['stage'] = 'dealer_turn'
    
    # 1. Show the dealer's hidden card before hitting
    await update_game_message(context, initial_status_message + "\n**Dealer is revealing cards...**")
    await asyncio.sleep(2) 
    
    dealer_value = get_hand_value(state['dealer_hand'])
    
    # 2. Dealer hits on < 17
    while dealer_value < 17:
        state['dealer_hand'].append(deal_card(state['deck']))
        dealer_value = get_hand_value(state['dealer_hand'])
        
        # Simulate delay and update for drama
        await asyncio.sleep(1.5) 
        await update_game_message(context, "Dealer hits...")

    # 3. Finalize the game
    await finalize_game_message(context)

# --- Telegram Command Handlers ---

async def start_game_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initializes a new multi-player game session and allows joining."""
    chat_data = context.chat_data
    
    if chat_data.get('blackjack_game') and chat_data['blackjack_game']['stage'] != 'finished':
        await update.message.reply_text("A game session is already active. Use **/deal** to start the game or wait for the current round to end.")
        return

    # Initialize a new game session
    chat_data['blackjack_game'] = {
        'deck': create_deck(),
        'dealer_hand': [],
        'players': {},
        'active_player': None,
        'stage': 'joining',
    }
    
    message = await update.message.reply_text(
        "♣️ **Multi-Player Blackjack Session Started!** ♦️\n"
        f"Up to **{MAX_PLAYERS}** players can join.\n\n"
        "Type **/join** to enter the game.\n"
        "Once ready, use **/deal** to start the round!",
        parse_mode=constants.ParseMode.MARKDOWN
    )
    chat_data['message_id'] = message.message_id # Store message ID for editing

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows a user to join the active game session."""
    chat_data = context.chat_data
    user = update.effective_user
    state = chat_data.get('blackjack_game')
    
    if not state or state['stage'] != 'joining':
        await update.message.reply_text("No active joining session. Use **/startgame** to begin.")
        return

    if user.id in state['players']:
        await update.message.reply_text(f"You ({user.first_name}) are already joined.")
        return
        
    if len(state['players']) >= MAX_PLAYERS:
        await update.message.reply_text("The game table is full! Use **/deal** to start.")
        return

    # Add player to state
    state['players'][user.id] = {'hand': [], 'status': 'playing', 'name': user.first_name}
    
    player_names = [p['name'] for p in state['players'].values()]
    
    # Update the start message to show who joined
    join_message = (
        "♣️ **Multi-Player Blackjack Session Started!** ♦️\n"
        f"**Joined Players ({len(state['players'])}/{MAX_PLAYERS}):**\n"
        f"  - {', '.join(player_names)}\n\n"
        "Type **/join** to enter the game.\n"
        "Once ready, use **/deal** to start the round!"
    )
    
    try:
        await context.bot.edit_message_text(
            chat_id=context.effective_chat.id, 
            message_id=chat_data['message_id'],
            text=join_message,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except telegram.error.BadRequest:
        # Ignore if the message is too old or failed to edit for some reason
        await update.message.reply_text(f"{user.first_name} joined the game. {len(state['players'])}/{MAX_PLAYERS} players ready.")


async def deal_hands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deals two cards to all joined players and the dealer, and sets the first active player."""
    chat_data = context.chat_data
    state = chat_data.get('blackjack_game')

    if not state or state['stage'] != 'joining':
        await update.message.reply_text("Cannot deal now. Use **/startgame** to begin a session first.")
        return
    
    if len(state['players']) == 0:
        await update.message.reply_text("No players joined! Need at least one player to start.")
        return

    state['stage'] = 'in_progress'
    
    # Deal to players
    for user_id in state['players']:
        player = state['players'][user_id]
        player['hand'] = [deal_card(state['deck']), deal_card(state['deck'])]
        
        # Check for immediate Blackjack
        if get_hand_value(player['hand']) == 21:
            player['status'] = 'blackjack'

    # Deal to dealer
    state['dealer_hand'] = [deal_card(state['deck']), deal_card(state['deck'])]
    
    # Set first active player (the first user ID in the players dictionary)
    first_player_id = list(state['players'].keys())[0]
    
    # Check if the first player immediately won with Blackjack
    if state['players'][first_player_id]['status'] == 'blackjack':
        # Skip this player's turn, move to the next
        state['active_player'] = first_player_id
        await move_to_next_player(context, f"{state['players'][first_player_id]['name']} has Blackjack! Moving to next player.")
    else:
        state['active_player'] = first_player_id
        await update_game_message(context, f"Hands dealt! It's **{state['players'][first_player_id]['name']}'s** turn. Choose action.", create_game_keyboard())


async def handle_game_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles HIT and STAND actions for the active player."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_data = context.chat_data
    action = query.data.split('_')[1]
    
    state = chat_data.get('blackjack_game')
    
    if not state or state['stage'] != 'in_progress':
        await query.edit_message_text("Game over or session expired. Use **/startgame** to start a new game.")
        return

    # Authorization Check
    if user_id != state['active_player']:
        # This will silently fail or pop up "It's not your turn!" message briefly
        await query.answer("It's not your turn!") 
        return
        
    player = state['players'][user_id]
    
    if action == 'hit':
        player['hand'].append(deal_card(state['deck']))
        player_value = get_hand_value(player['hand'])
        
        if player_value > 21:
            player['status'] = 'bust'
            status_msg = f"{player['name']} BUSTS! Moving to the next player."
            await move_to_next_player(context, status_msg)
        else:
            await update_game_message(context, f"{player['name']} hits. Choose action.", create_game_keyboard())
            
    elif action == 'stand':
        player['status'] = 'stand'
        status_msg = f"{player['name']} STANDS. Moving to the next player."
        await move_to_next_player(context, status_msg)

# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    # Use /start and /startgame to begin the joining phase
    application.add_handler(CommandHandler("start", start_game_session))
    application.add_handler(CommandHandler("startgame", start_game_session))
    
    # Handlers for the multi-player flow
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("deal", deal_hands))

    # Action handler for HIT/STAND buttons
    application.add_handler(CallbackQueryHandler(handle_game_action, pattern="^action_"))

    print("Multi-Player Blackjack Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
