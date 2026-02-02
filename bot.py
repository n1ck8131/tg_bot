"""
Точка входа (для обратной совместимости).
Рекомендуется использовать: python run.py или python -m app.bot
"""

import asyncio
from app.bot import main

if __name__ == "__main__":
    asyncio.run(main())
