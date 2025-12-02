def main():
    """Starts the bot."""
    application = ApplicationBuilder().token(TOKEN).build()

    # Old single-player command can now start the multi-game flow
    application.add_handler(CommandHandler("start", start_game_session))
    application.add_handler(CommandHandler("startgame", start_game_session))
    
    # New handlers for the multi-player flow
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CommandHandler("deal", deal_hands))

    # Action handler must now use the multi-player logic
    application.add_handler(CallbackQueryHandler(handle_game_action_multi, pattern="^action_"))

    print("Multi-Player Blackjack Bot is running... Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == '__main__':
    main()
