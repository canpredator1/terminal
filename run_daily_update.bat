@echo off
echo =========================================
echo Starting Daily Semiconductor Pipeline Run
echo Date: %date% %time%
echo =========================================

:: 1. Update daily stock prices & market regime
echo Running Market Pipeline (Prices)...
.venv\Scripts\python -m src.pipeline_daily_market

:: 2. Update news, fundamentals, and events
echo Running Secondary Pipeline (News)...
.venv\Scripts\python -m src.pipeline_secondary

:: 3. Generate AI Sentiment scores
echo Running AI Sentiment Pipeline (Gemini)...
:: Load the .env file if it exists
for /f "tokens=*" %%a in (.env) do set %%a
.venv\Scripts\python -m src.pipeline_ai_sentiment

:: 4. Generate Macro Sector & Market Sentiment
echo Running Macro Sentiment Pipeline (Gemini)...
.venv\Scripts\python -m src.pipeline_macro_sentiment

:: 5. Regenerate the Map HTML
echo Regenerating Map HTML...
.venv\Scripts\python -m src.generate_enhanced_map

echo =========================================
echo Daily Pipeline Run Complete!
echo =========================================
pause
