"""
Pool de browsers Playwright assíncronos e reutilizáveis.

Cria um número fixo de contextos de browser (MAX_WORKERS) e distribui
as tarefas de crawling por eles, evitando o overhead de abrir e fechar
um browser por cada URL.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import MAX_WORKERS, REQUEST_TIMEOUT_MS

logger = logging.getLogger(__name__)


class BrowserPool:
    """
    Pool de contextos Playwright para reutilização eficiente.

    Uso:
        pool = BrowserPool(size=10)
        await pool.start()
        async with pool.acquire() as page:
            await page.goto("https://exemplo.pt")
        await pool.stop()
    """

    def __init__(self, size: int = MAX_WORKERS, headless: bool = True):
        self.size = size
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._contexts: list[BrowserContext] = []
        self._context_queue: Optional[asyncio.Queue] = None

    async def start(self) -> None:
        """Inicia o Playwright e cria os contextos do pool."""
        logger.info(f"A iniciar BrowserPool com {self.size} workers...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._context_queue = asyncio.Queue()

        for i in range(self.size):
            ctx = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="pt-PT",
            )
            self._contexts.append(ctx)
            await self._context_queue.put(ctx)

        logger.info("BrowserPool iniciado.")

    async def stop(self) -> None:
        """Fecha todos os contextos e o browser."""
        logger.info("A fechar BrowserPool...")
        for ctx in self._contexts:
            try:
                await ctx.close()
            except Exception:
                pass
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("BrowserPool fechado.")

    @asynccontextmanager
    async def acquire(self):
        """
        Context manager que cede uma Page de um contexto disponível.
        Bloqueia se não houver contextos livres.
        """
        ctx: BrowserContext = await self._context_queue.get()
        page: Optional[Page] = None
        try:
            page = await ctx.new_page()
            page.set_default_timeout(REQUEST_TIMEOUT_MS)
            # Bloquear recursos desnecessários para acelerar o carregamento
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}",
                lambda route: route.abort()
                if _should_block(route.request.url)
                else route.continue_(),
            )
            yield page
        finally:
            if page and not page.is_closed():
                await page.close()
            await self._context_queue.put(ctx)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()


def _should_block(url: str) -> bool:
    """Bloqueia imagens e fontes mas permite SVG inline de logos."""
    blocked_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp",
                          ".woff", ".woff2", ".ttf", ".eot")
    return any(url.lower().split("?")[0].endswith(ext)
               for ext in blocked_extensions)
