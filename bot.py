import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
import random
import json
import os
from itertools import combinations
import re 
import asyncio 

# --- Configuration & Security ---
# Load TOKEN from environment variable for production (Best Practice). 
# Fallback is for testing only.
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M') 
DATA_FILE = 'data.json'
SIX_COLORS = ['🔵 Blue', '🔴 Red', '🟢 Green', '🟡 Yellow', '⚪ White', '🌸 Pink']
ROLLS_PER_GAME = 3 
BUTTON_TEXT = "View External Report" 

# --- State Management ---
# Tracks the user's current roll: {user_id: [color_1, color_2, color_3]}
USER_ROLL_STATE = {}

# --- Data Management Functions ---

def load_data():
    """Loads history, counts, and configuration (including URL and credentials) from the JSON file."""
    default_data = {
        "history": [],
        "color_counts": {color: 0 for color in SIX_COLORS},
        "config": {
            "analysis_url_base": "https://queenking.ph/game/play/STUDIO-CGM-CGM002-by-we", 
            "username": "09925345945", 
            "password": "Shiwashi21"    
        }
    }
    if not os.path.exists(DATA_FILE):
        return default_data
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # Ensure all necessary keys exist (robust loading)
            data.setdefault('config', default_data['config'])
            data.setdefault('color_counts', default_data['color_counts'])
            for key in default_data['config']:
                data['config'].setdefault(key, default_data['config'][key])
            for color in SIX_COLORS:
                data['color_counts'].setdefault(color, 0)
            return data
    except json.JSONDecodeError:
        return default_data

def save_data(data):
    """Saves the current data state to the JSON file."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

def update_data_with_roll(rolled_colors, data):
    """Updates history and color counts after a roll."""
    data['history'].append(rolled_colors)
    for color in rolled_colors:
        data['color_counts'][color] += 1
    save_data(data)

# --- Analysis & Utility Functions ---

def create_color_keyboard(roll_number):
    """Creates the inline keyboard with color buttons."""
    keyboard = [
        [InlineKeyboardButton("🔵 Blue", callback_data=f"roll_{roll_number}_Blue"),
         InlineKeyboardButton("🔴 Red", callback_data=f"roll_{roll_number}_Red")],
        [InlineKeyboardButton("🟢 Green", callback_data=f"roll_{roll_number}_Green"),
         InlineKeyboardButton("🟡 Yellow", callback_data=f"roll_{roll_number}_Yellow")],
        [InlineKeyboardButton("⚪ White", callback_data=f"roll_{roll_number}_White"),
         InlineKeyboardButton("🌸 Pink", callback_data=f"roll_{roll_number}_Pink")],
    ]
    return InlineKeyboardMarkup(keyboard)

def analyze_patterns(data):
    """Calculates historical probabilities and identifies short-term trends (Full History)."""
    total_rolls = sum(data['color_counts'].values())
    if total_rolls == 0:
        return "No history yet. Get more rolls to see patterns!"

    probabilities = {}
    for color, count in data['color_counts'].items():
        probabilities[color] = count / total_rolls

    sorted_probs = sorted(probabilities.items(), key=lambda item: item[1])
    least_likely = sorted_probs[0]
    most_likely = sorted_probs[-1]
    
    count_details = "\n".join([f"- {color}: {count} hits" for color, count in sorted(data['color_counts'].items())])

    full_history_msg = (
        f"--- **Full History Analysis** ---\n"
        f"Based on **{total_rolls}** total individual dice rolls:\n"
        f"**Symbol Counts:**\n{count_details}\n"
        f"🥇 **Most Frequent:** {most_likely[0]} ({most_likely[1]:.2%})\n"
        f"📉 **Least Frequent:** {least_likely[0]} ({least_likely[1]:.2%})"
    )
    return full_history_msg

def find_coldest_color(data):
    """Identifies the color that has not appeared for the longest consecutive number of rolls."""
    history = data['history']
    if not history:
        return "\n🥶 **Coldest Color Tracker:** No rolls logged yet." 

    coldest_streaks = {}
    
    for color in SIX_COLORS:
        streak_count = 0
        for roll in reversed(history):
            if color in roll:
                break
            else:
                streak_count += 1
        coldest_streaks[color] = streak_count
    
    coldest_color = max(coldest_streaks, key=coldest_streaks.get)
    coldest_streak_length = coldest_streaks[coldest_color]
    
    if coldest_streak_length == 0:
        return "\n🥶 **Coldest Color Tracker:** All colors appeared in the last roll."

    message = (
        f"\n🥶 **Coldest Color Tracker (Martingale Suggestion):**\n"
        f"**{coldest_color}** missed **{coldest_streak_length}** rolls. (Statistically 'due')."
    )
    return message

def predict_combinations(data):
    """Analyzes historical data to predict the three most likely 3-color outcomes."""
    history = data['history']
    
    if len(history) < 10: 
        return "\n--- **Combination Prediction** ---\nNeed at least 10 rolls for reliable prediction."

    color_counts = data['color_counts']
    most_frequent_color = max(color_counts, key=color_counts.get)
    
    pair_counts = {}
    for roll in history:
        unique_roll_colors = list(set(roll))
        for combo in combinations(unique_roll_colors, 2):
            sorted_combo = tuple(sorted(combo))
            pair_counts[sorted_combo] = pair_counts.get(sorted_combo, 0) + 1

    if not pair_counts:
          color_B, color_C = most_frequent_color, most_frequent_color
    else:
        most_frequent_pair = max(pair_counts, key=pair_counts.get)
        color_B, color_C = most_frequent_pair
        
    prediction_1 = [color_B, color_C, most_frequent_color]
    random.shuffle(prediction_1) 
    
    prediction_2_base = [color_B, color_C] 
    if color_B == color_C:
        sorted_counts = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)
        third_color = sorted_counts[1][0] if len(sorted_counts) > 1 else SIX_COLORS[0]
        prediction_2 = [color_B, color_C, third_color]
    else:
        prediction_2 = [color_B, color_C, color_B] 
        
    random.shuffle(prediction_2)  
    
    prediction_3 = [most_frequent_color, most_frequent_color, most_frequent_color]

    pred1_str = ' | '.join(prediction_1)
    pred2_str = ' | '.join(prediction_2)
    pred3_str = ' | '.join(prediction_3)
    
    message = (
        f"\n--- **Combination Prediction** ---\n"
        f"Based on **{len(history)}** past rolls:\n"
        f"🥇 **P1 (Mix):** `{pred1_str}` (Pair Freq. + Individual Freq.)\n"
        f"🥈 **P2 (Double):** `{pred2_str}` (Double Pair Color)\n"
        f"🔱 **P3 (Jackpot):** `{pred3_str}` (Triple Freq. Color)"
    )
    
    return message

def format_last_15_rolls(data):
    """Formats the last 15 full rolls for display."""
    history = data['history']
    
    if not history:
        return "History: No rolls logged yet."
        
    recent_history = history[-15:] 
    
    start_index = len(history) - len(recent_history) + 1
    
    roll_list = []
    for i, roll in enumerate(recent_history):
        roll_str = f"**#{start_index + i}:** " + " | ".join(roll)
        roll_list.append(roll_str)
        
    formatted_history = "\n".join(roll_list)
    
    return (
        f"📜 **Last {len(recent_history)} Logged Rolls (Batches):**\n"
        f"{formatted_history}"
    )

# --- Command Handlers ---

async def reset_history(update, context):
    """Resets all recorded history and counts."""
    initial_data = load_data() 
    initial_data['history'] = []
    initial_data['color_counts'] = {color: 0 for color in SIX_COLORS}
    save_data(initial_data)
    await update.message.reply_text(
        "✅ **Prediction History Reset!** All past rolls and statistics have been cleared.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def start(update, context):
    """Sends a greeting message with a full list of commands."""
    welcome_message = (
        "Welcome! I analyze the Philippine Color Game 3-Dice Roll using statistics.\n\n"
        "### 🕹️ **Game Commands**\n"
        "Use these commands to input results and get predictions:\n"
        "• **/roll** or **/predict**: Start the button-selection process to log a new result and get the next prediction.\n"
        "• **/analyze**: View the full statistical breakdown, last 15 rolls, and the best predicted combination.\n\n"
        "### ⚙️ **Administrative Commands**\n"
        "Use these to manage data and links:\n"
        "• **/setbaseurl [url]**: Set the base URL for the external analysis report.\n"
        "• **/setcreds [user] [pass]**: Set the username and password used to access the analysis link.\n"
        "• **/reset**: Clear all logged history and statistics (DANGEROUS!)."
    )
    await update.message.reply_text(welcome_message, parse_mode=constants.ParseMode.MARKDOWN)

async def set_analysis_base_url(update, context):
    """Allows the user to set a new base external URL for the /analyze button."""
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please provide the base URL after the command.\n\n"
            "Example: **/setbaseurl https://your-website.com/report**",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    new_base_url = context.args[0]
        
    data = load_data()
    data['config']['analysis_url_base'] = new_base_url
    save_data(data)
    
    await update.message.reply_text(
        f"✅ **Analysis Base URL Updated!**\n"
        f"The new base URL is: `{new_base_url}`.\n"
        f"This link will be used when you type **/analyze**.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def set_credentials(update, context):
    """Allows the user to set their username and password for the analysis URL."""
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Please provide both your **username** and **password**.\n\n"
            "Example: **/setcreds your_username your_password**",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    username = context.args[0]
    password = context.args[1]
    
    data = load_data()
    data['config']['username'] = username
    data['config']['password'] = password
    save_data(data)
    
    await update.message.reply_text(
        f"✅ **Credentials Saved!**\n"
        f"Username: `{username}`\n"
        f"Your analysis link will now be generated with these credentials.",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def start_roll(update, context):
    """Starts the 3-dice color selection process via buttons. This is used by /roll, /predict, and the new button callback."""
    user_id = update.effective_user.id
    
    USER_ROLL_STATE[user_id] = [None, None, None]
    
    keyboard = create_color_keyboard(roll_number=1)
    
    # We use update.message.reply_text here as this is triggered by a command (/roll or /predict)
    await update.message.reply_text(
        "🎲 **Roll 1 of 3:** Please select the color for the first die.",
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def start_roll_from_callback(update, context):
    """Handles the 'start_new_roll' callback from the button to initiate the /roll sequence."""
    query = update.callback_query
    await query.answer("Starting new roll sequence...")
    
    user_id = query.from_user.id
    USER_ROLL_STATE[user_id] = [None, None, None]
    keyboard = create_color_keyboard(roll_number=1)
    
    # Edit the previous analysis message to start the roll sequence
    await query.edit_message_text(
        "🎲 **Roll 1 of 3:** Please select the color for the first die.",
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_color_callback(update, context):
    """Handles color selection button clicks and tracks state."""
    query = update.callback_query
    # Immediate answer to prevent loading spinner (0 delay user experience)
    await query.answer() 
    
    user_id = query.from_user.id
    data = query.data.split('_')
    
    # Only proceed if this is a color roll callback and a session exists
    if data[0] != 'roll' or user_id not in USER_ROLL_STATE:
        return 

    roll_number = int(data[1])
    selected_color = data[2] 
    
    full_color_name = next((c for c in SIX_COLORS if selected_color in c), None)
    
    USER_ROLL_STATE[user_id][roll_number - 1] = full_color_name

    if roll_number == 3:
        # Final roll, save data and generate prediction
        rolled_colors = USER_ROLL_STATE.pop(user_id)
        
        game_data = load_data()
        update_data_with_roll(rolled_colors, game_data)
        
        individual_analysis = analyze_patterns(game_data)
        coldness_analysis = find_coldest_color(game_data)
        combination_analysis = predict_combinations(game_data)

        # 1. Extract the Best Prediction Summary
        best_prediction_summary = "Prediction not yet available (Need 10+ rolls)."
        if len(game_data['history']) >= 10:
            try:
                p1_line = next(line for line in combination_analysis.split('\n') if line.startswith('🥇 **P1 (Mix):**'))
                best_prediction_summary = re.sub(r'🥇 \*\*P1 \(Mix\):\*\* `(.*?)`.*', r'\1', p1_line).strip()
            except StopIteration:
                pass 
                
        # 2. Consolidate the Final Response, prominently featuring the next prediction
        full_analysis_message = (
            "✅ **Roll Logged!**\n"
            f"**Logged Lineup:** {rolled_colors[0]} | {rolled_colors[1]} | {rolled_colors[2]}\n\n"
            "--- **Statistical Prediction for NEXT Roll** ---\n"
            f"🎯 **RECOMMENDED NEXT ROLL (P1):** `{best_prediction_summary}`\n\n"
            
            f"{individual_analysis}\n\n"
            f"{coldness_analysis}\n"
            f"{combination_analysis}" 
        )
        
        # 3. ADD THE NEW BUTTON to start the next roll
        keyboard = [[InlineKeyboardButton("Submit Next Roll / Predict", callback_data="start_new_roll")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            full_analysis_message,
            reply_markup=reply_markup, 
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    # Not the final roll, prompt for the next die
    next_roll_number = roll_number + 1
    keyboard = create_color_keyboard(next_roll_number)
    
    await query.edit_message_text(
        f"🎲 **Roll {next_roll_number} of 3:** Color set to **{full_color_name}**. Select the next color.",
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    
async def get_analysis_only(update, context):
    """Allows the user to view the full analysis based on ALL history, and includes an external URL button."""
    
    data = load_data()
    
    # Get configuration data
    base_url = data['config'].get('analysis_url_base', "https://www.example.com/report")
    username = data['config'].get('username', '')
    password = data['config'].get('password', '')
    
    # 1. CONSTRUCT THE AUTHENTICATED URL
    if username and password:
        if '://' in base_url:
            protocol_match = re.match(r"^(https?://|ftp://)", base_url)
            if protocol_match:
                protocol = protocol_match.group(0)
                domain_path = base_url[len(protocol):]
                analysis_url = f"{protocol}{username}:{password}@{domain_path}"
            else:
                analysis_url = f"https://{username}:{password}@{base_url}"
        else:
            analysis_url = f"https://{username}:{password}@{base_url}"
        
        url_status = f"🔐 Link generated with saved credentials."
    else:
        analysis_url = base_url
        url_status = f"🔗 Link is using the base URL (credentials not set)."

    # 2. Format and display the recorded history (Last 15 Rolls)
    history_display_15 = format_last_15_rolls(data)
    
    # 3. Perform all analyses
    individual_analysis = analyze_patterns(data)
    coldness_analysis = find_coldest_color(data)
    combination_analysis = predict_combinations(data)

    # 4. Extract the Best Prediction Summary
    best_prediction_summary = "Prediction not yet available (Need 10+ rolls)."
    if len(data['history']) >= 10:
        try:
            p1_line = next(line for line in combination_analysis.split('\n') if line.startswith('🥇 **P1 (Mix):**'))
            best_prediction_summary = re.sub(r'🥇 \*\*P1 \(Mix\):\*\* `(.*?)`.*', r'\1', p1_line).strip()
        except StopIteration:
            pass 

    # 5. Consolidate message
    full_analysis_message = (
        f"{history_display_15}\n"
        f"--- **Best Prediction Summary** ---\n"
        f"🎯 **RECOMMENDED NEXT ROLL (P1):** `{best_prediction_summary}`\n\n"
        f"--- **Full Statistical Breakdown** ---\n"
        f"Total Batches Logged: **{len(data['history'])}**.\n\n"
        f"{individual_analysis}\n\n"
        f"{coldness_analysis}\n"
        f"{combination_analysis}\n"
        f"{url_status}"
    )

    # 6. Create the Inline Keyboard button (Report and Next Roll)
    keyboard = [
        # Existing row for the external report link
        [InlineKeyboardButton(BUTTON_TEXT, url=analysis_url)],
        # NEW ROW for submitting the next roll
        [InlineKeyboardButton("Submit Next Roll / Predict", callback_data="start_new_roll")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        full_analysis_message, 
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- Main Bot Execution ---

def main():
    """Starts the bot."""
    if not os.path.exists(DATA_FILE):
        save_data(load_data())
    
    # The ApplicationBuilder handles the setup
    application = ApplicationBuilder().token(TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("roll", start_roll))
    application.add_handler(CommandHandler("predict", start_roll))
    application.add_handler(CommandHandler("analyze", get_analysis_only))
    application.add_handler(CommandHandler("setbaseurl", set_analysis_base_url)) 
    application.add_handler(CommandHandler("setcreds", set_credentials)) 
    application.add_handler(CommandHandler("reset", reset_history))

    # Register callback handlers
    # This handles the "Submit Next Roll" button from the analysis screens
    application.add_handler(CallbackQueryHandler(start_roll_from_callback, pattern="^start_new_roll$")) 
    # This handles all the individual color selection clicks (roll_1_color, roll_2_color, etc.)
    # It must be placed after the specific pattern handler above.
    application.add_handler(CallbackQueryHandler(handle_color_callback)) 

    print("Color Dice Roll Predictor Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
