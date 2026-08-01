#!/bin/bash
cd /home/shahab/bot/boutique_erp

echo "🚀 Starting database..."
docker compose up -d db

echo "⏳ Waiting for database to be healthy..."
sleep 5

echo "🔄 Applying database migrations..."
export PATH="$HOME/.local/bin:$PATH"
alembic upgrade head

echo "✅ Database is ready!"
echo "🚀 Starting the Bot..."
python3 -m app.main
