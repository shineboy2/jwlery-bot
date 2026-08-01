#!/bin/bash
# Auto-start script for boutique ERP bot
LOG_FILE="/home/shahab/bot/boutique_erp/bot_startup.log"
BOT_DIR="/home/shahab/bot/boutique_erp"

echo "=== Bot Startup: $(date) ===" >> "$LOG_FILE"

# Step 1: Start PostgreSQL Docker container
docker start boutique_erp-db-1 >> "$LOG_FILE" 2>&1
sleep 4

# Step 2: Kill any old bot process
pkill -f "python3 -m app.main" 2>/dev/null

# Step 3: Start the bot
export PATH="$HOME/.local/bin:$PATH"
cd "$BOT_DIR"
nohup python3 -m app.main >> "$LOG_FILE" 2>&1 &
echo "Bot started with PID: $!" >> "$LOG_FILE"
