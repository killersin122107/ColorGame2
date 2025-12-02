import telegram
from telegram.ext import CommandHandler, ApplicationBuilder, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, constants
import random
import json
import os
from itertools import combinations
import re 

# --- Configuration ---
# Telegram Bot Token provided by the user
TOKEN = '8103644321:AAFDyGgp2G-0TXDkMV8iXY4VuGg5iYY7H-M' 
DATA_FILE = 'data.json'
SIX_COLORS = ['🔵 Blue', '🔴 Red', '🟢 Green', '🟡 Yellow', '⚪ White', '🌸 Pink']
BUTTON_TEXT = "View Detailed Report"
PREDICT_BUTTON = "➡️ Log Next Roll / Predict" 

# --- State Management ---
# Tracks the user's current roll for the multi-step process: {user_id: [color_1, color_2, color_3]}
USER_ROLL_STATE = {}

# --- Data Management Functions ---

def load_data():
    """Loads history, counts, and configuration from the JSON file."""
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
            data.setdefault('config', default_data['config'])
            for key in default_data['config']:
                data['config'].setdefault(key, default_data['config'][key])
            data.setdefault('color_counts', default_data['color_counts'])
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

# --- Analysis & Prediction Functions (Unchanged from previous versions) ---

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
        
    # P1: Mix - Most Frequent Pair + Most Frequent Individual Color
    prediction_1 = sorted([color_B, color_C, most_frequent_color])
    
    # P2: Double - Most Frequent Pair + One color from the pair repeated
    prediction_2 = sorted([color_B, color_C, color_B if color_B != color_C else SIX_COLORS[0]]) 
    
    # P3: Jackpot - Triple Most Frequent Color
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

async def start(update, context):
    """Sends a greeting message with a full list of commands."""
    welcome_message = (
        "Welcome! I analyze the Philippine Color Game 3-Dice Roll using statistics.\n\n"
        "### 🕹️ **Game Commands (Quickest Options First)**\n"
        "• **/log [C1] [C2] [C3]**: **(FASTEST)** Log all three colors at once. *e.g., /log Blue Green Red*\n"
        "• **/roll** or **/predict**: Start the 3-step button-selection process.\n"
        "• **/analyze**: View the full statistical breakdown, last 15 rolls, and the best prediction.\n\n"
        "### ⚙️ **Administrative Commands**\n"
        "• **/setbaseurl [url]**: Set the base URL for the external analysis report.\n"
        "• **/setcreds [user] [pass]**: Set the username and password.\n"
        "• **/reset**: Clear all logged history (DANGEROUS!)."
    )
    await update.message.reply_text(welcome_message, parse_mode=constants.ParseMode.MARKDOWN)

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
        f"The new base URL is: `{new_base_url}`.",
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
        f"Username: `{username}`",
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- NEW QUICK LOGGING LOGIC ---

def validate_colors(args):
    """Validates if the three arguments provided are valid colors."""
    valid_colors = [c.split()[1] for c in SIX_COLORS]
    
    if len(args) != 3:
        return False, "⚠️ Please provide exactly **three** colors."

    validated_colors = []
    
    for arg in args:
        match = next((full_color for full_color in SIX_COLORS if arg.lower() == full_color.split()[1].lower()), None)
        
        if not match:
            return False, f"❌ Invalid color: **{arg}**. Valid options are: {'/'.join(valid_colors)}."
        
        validated_colors.append(match) 
        
    return True, validated_colors


async def log_quick_roll(update, context):
    """Handles /log command: Logs a 3-color roll directly via command arguments and returns the prediction."""
    
    is_valid, result = validate_colors(context.args)

    if not is_valid:
        await update.message.reply_text(
            f"{result}\n\nExample: **/log Blue Green Yellow**",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    rolled_colors = result
    game_data = load_data()
    update_data_with_roll(rolled_colors, game_data)
    
    roll_message = (
        f"✅ **Quick Roll Logged!**\n"
        f"**Logged Lineup:** {rolled_colors[0]} | {rolled_colors[1]} | {rolled_colors[2]}\n\n"
    )
    
    individual_analysis = analyze_patterns(game_data)
    coldness_analysis = find_coldest_color(game_data)
    combination_analysis = predict_combinations(game_data)
    
    full_analysis_message = (
        f"{roll_message}"
        f"--- **Statistical Prediction for NEXT Roll** ---\n\n"
        f"{individual_analysis}\n\n"
        f"{coldness_analysis}\n"
        f"{combination_analysis}"
    )

    predict_keyboard = [[InlineKeyboardButton(PREDICT_BUTTON, callback_data="command_predict")]]
    predict_reply_markup = InlineKeyboardMarkup(predict_keyboard)
    
    await update.message.reply_text(
        full_analysis_message,
        reply_markup=predict_reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- MULTI-STEP LOGIC ---

async def start_roll(update, context):
    """Starts the 3-dice color selection process via buttons (for /roll and /predict)."""
    user_id = update.effective_user.id
    
    USER_ROLL_STATE[user_id] = [None, None, None]
    keyboard = create_color_keyboard(roll_number=1)
    
    await update.message.reply_text(
        "🎲 **Roll 1 of 3:** Please select the color for the first die.",
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_color_callback(update, context):
    """Handles color selection button clicks for the 3-step process."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data.split('_')
    
    if len(data) != 3 or user_id not in USER_ROLL_STATE:
        await query.edit_message_text("Error: Roll session timed out or invalid data. Use /roll to start again.")
        return

    roll_number = int(data[1])
    selected_color = data[2] 
    full_color_name = next((c for c in SIX_COLORS if selected_color in c), None)
    
    USER_ROLL_STATE[user_id][roll_number - 1] = full_color_name

    if roll_number == 3:
        # Final roll: save data, generate prediction, and add the quick re-roll button.
        rolled_colors = USER_ROLL_STATE.pop(user_id)
        
        game_data = load_data()
        update_data_with_roll(rolled_colors, game_data)
        
        roll_message = (
            f"✅ **Roll Logged!**\n"
            f"**Logged Lineup:** {rolled_colors[0]} | {rolled_colors[1]} | {rolled_colors[2]}\n\n"
        )
        
        individual_analysis = analyze_patterns(game_data)
        coldness_analysis = find_coldest_color(game_data)
        combination_analysis = predict_combinations(game_data)
        
        full_analysis_message = (
            f"{roll_message}"
            f"--- **Statistical Prediction for NEXT Roll** ---\n\n"
            f"{individual_analysis}\n\n"
            f"{coldness_analysis}\n"
            f"{combination_analysis}"
        )

        predict_keyboard = [[InlineKeyboardButton(PREDICT_BUTTON, callback_data="command_predict")]]
        predict_reply_markup = InlineKeyboardMarkup(predict_keyboard)
        
        await query.edit_message_text(
            full_analysis_message,
            reply_markup=predict_reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    # Not the final roll: immediately prompt for the next die (zero delay)
    next_roll_number = roll_number + 1
    keyboard = create_color_keyboard(next_roll_number)
    
    await query.edit_message_text(
        f"🎲 **Roll {next_roll_number} of 3:** Color set to **{full_color_name}**. Select the next color.",
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    
async def handle_command_callback(update, context):
    """Handles callback for in-line buttons that trigger commands (like /predict)."""
    query = update.callback_query
    await query.answer()
    
    command = query.data.split('_')[1]

    if command == 'predict':
        # Restart the multi-step rolling process (start_roll logic)
        user_id = query.from_user.id
        USER_ROLL_STATE[user_id] = [None, None, None]
        keyboard = create_color_keyboard(roll_number=1)

        await query.edit_message_text(
            "🎲 **Roll 1 of 3:** Please select the color for the first die.",
            reply_markup=keyboard,
            parse_mode=constants.ParseMode.MARKDOWN
        )

async def get_analysis_only(update, context):
    """Allows the user to view the full analysis based on ALL history, and includes an external URL button."""
    
    data = load_data()
    
    base_url = data['config'].get('analysis_url_base', "https://www.example.com/report")
    username = data['config'].get('username', '')
    password = data['config'].get('password', '')
    
    # CONSTRUCT THE AUTHENTICATED URL
    if username and password:
        protocol_match = re.match(r"^(https?://|ftp://)", base_url)
        if protocol_match:
            protocol = protocol_match.group(0)
            domain_path = base_url[len(protocol):]
            analysis_url = f"{protocol}{username}:{password}@{domain_path}"
        else:
            analysis_url = f"https://{username}:{password}@{base_url}"
        url_status = f"🔐 Link generated with saved credentials."
    else:
        analysis_url = base_url
        url_status = f"🔗 Link is using the base URL (credentials not set)."

    history_display_15 = format_last_15_rolls(data)
    individual_analysis = analyze_patterns(data)
    coldness_analysis = find_coldest_color(data)
    combination_analysis = predict_combinations(data)

    best_prediction_summary = "Prediction not yet available (Need 10+ rolls)."
    if len(data['history']) >= 10:
        try:
            p1_line = next(line for line in combination_analysis.split('\n') if line.startswith('🥇 **P1 (Mix):**'))
            best_prediction_summary = re.sub(r'🥇 \*\*P1 \(Mix\):\*\* `(.*?)`.*', r'\1', p1_line).strip()
        except StopIteration:
            pass 

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

    keyboard = [[InlineKeyboardButton(BUTTON_TEXT, url=analysis_url)]]
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
    
    application = ApplicationBuilder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    
    # 1. Quick Log (New)
    application.add_handler(CommandHandler("log", log_quick_roll))
    
    # 2. Multi-Step Roll (Original)
    application.add_handler(CommandHandler("roll", start_roll))
    application.add_handler(CommandHandler("predict", start_roll))
    application.add_handler(CallbackQueryHandler(handle_color_callback, pattern=r'^roll_\d+_[A-Za-z]+$'))
    application.add_handler(CallbackQueryHandler(handle_command_callback, pattern=r'^command_[A-Za-z]+$'))
    
    # 3. Administrative Commands
    application.add_handler(CommandHandler("analyze", get_analysis_only))
    application.add_handler(CommandHandler("setbaseurl", set_analysis_base_url)) 
    application.add_handler(CommandHandler("setcreds", set_credentials)) 
    application.add_handler(CommandHandler("reset", reset_history))

    print("Color Dice Roll Predictor Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
