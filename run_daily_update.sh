#!/bin/bash

echo "========================================="
echo "Starting Daily Semiconductor Pipeline Run"
echo "Date: $(date)"
echo "========================================="

# Move to the project directory
cd /Users/cansuer/Desktop/new/semiconductor_earnings_reaction

# 1. Update daily stock prices & market regime
echo "Running Market Pipeline (Prices)..."
.venv/bin/python3 -m src.pipeline_daily_market

# 2. Update news, fundamentals, and events
echo "Running Secondary Pipeline (News)..."
.venv/bin/python3 -m src.pipeline_secondary

# 3. Generate AI Sentiment scores
echo "Running AI Sentiment Pipeline (Gemini)..."
source .env
.venv/bin/python3 -m src.pipeline_ai_sentiment

# 4. Generate Macro Sector & Market Sentiment
echo "Running Macro Sentiment Pipeline (Gemini)..."
.venv/bin/python3 -m src.pipeline_macro_sentiment

# 5. Regenerate the Map HTML
echo "Regenerating Map HTML..."
.venv/bin/python3 -m src.generate_enhanced_map

echo "========================================="
echo "Daily Pipeline Run Complete!"
echo "========================================="
