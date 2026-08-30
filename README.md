# Miss Ellie VK Pre-A1 diagnostic bot

Ready-to-deploy VK community bot for the course submission.

Included:
- 20 fixed Pre-A1 / Starters questions and all question images
- A/B/C buttons
- 2 emeralds for a correct answer, 1 emerald for bravery if wrong
- structured error tracking across 10 topics
- 4-step emerald shop (house, garden, pet, decor) for budgets 20–40
- final shop image composed automatically from transparent PNG layers (optimized for deployment)
- pet is always rendered LAST and therefore stays in the foreground
- AI-generated parent report from de-identified diagnostic data
- checker stub for VK ID 2840329

## Start
Python entry point: `bot.py`
Dependencies: `requirements.txt`

The bot accepts a VK community token from either `VK_TOKEN` or Bothost's `BOT_TOKEN`.
It tries to determine the community ID automatically; `VK_GROUP_ID` is only a fallback if auto-detection fails.

AI variables:
- `AI_API_URL`
- `AI_API_KEY`
- `AI_MODEL`

Do not commit real API keys or tokens to GitHub.
