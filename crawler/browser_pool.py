"""
Pool de browsers Playwright assíncronos e reutilizáveis.

Cria um número fixo de contextos de browser (MAX_WORKERS) e distribui
as tarefas de crawling por eles, evitando o overhead de abrir e fechar
um browser por cada URL.

Inclui stealth mode (playwright-stealth) e fallback HTTP (httpx) para
lidar com respostas 403 de protecções anti-bot.

Instalação dos requisitos adicionais:
    pip install playwright-stealth httpx
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "playwright-stealth não instalado. "
        "Execute: pip install playwright-stealth"
    )

from config import MAX_WORKERS, REQUEST_TIMEOUT_MS, HTTP_ONLY_DOMAINS, KNOWN_BLOCKED_DOMAINS

logger = logging.getLogger(__name__)

# User-agents rotativos — alterna por contexto para reduzir fingerprinting
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

_REALISTIC_HEADERS = {
    "Accept-Language": "pt-PT,pt;q=0.9,en-GB;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


class BrowserPool:
    """
    Pool de contextos Playwright para reutilização eficiente.

    Estratégia anti-403 (por ordem de tentativa):
        1. Playwright + stealth_async + headers realistas
        2. Fallback HTTP puro via httpx (para sites que bloqueiam headless)
        3. Marcar como bloqueado e continuar

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
        self._contexts: list[BrowserContext] = []
        self._context_queue: Optional[asyncio.Queue] = None

    async def start(self) -> None:
        """Inicia o Playwright e cria os contextos do pool."""
        logger.info(f"A iniciar BrowserPool ({self.size} workers, stealth={STEALTH_AVAILABLE})...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                # Flags adicionais para reduzir fingerprint de headless
                "--disable-infobars",
                "--disable-background-timer-throttling",
                "--disable-popup-blocking",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ],
        )
        self._context_queue = asyncio.Queue()

        for i in range(self.size):
            ctx = await self._browser.new_context(
                user_agent=_USER_AGENTS[i % len(_USER_AGENTS)],
                viewport={"width": 1280, "height": 800},
                locale="pt-PT",
                timezone_id="Europe/Lisbon",
                extra_http_headers=_REALISTIC_HEADERS,
                # Simular preferências reais de browser
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=False,
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
        Aplica stealth_async automaticamente se disponível.
        """
        ctx: BrowserContext = await self._context_queue.get()
        page: Optional[Page] = None
        try:
            page = await ctx.new_page()
            page.set_default_timeout(REQUEST_TIMEOUT_MS)

            # ── Stealth mode ──────────────────────────────────────────────────
            # Remove navigator.webdriver, plugins[], languages[], e outras
            # propriedades que os sistemas anti-bot detetam em headless.
            if STEALTH_AVAILABLE:
                await stealth_async(page)
            else:
                # Fallback manual mínimo se playwright-stealth não estiver instalado
                await page.add_init_script(_MANUAL_STEALTH_SCRIPT)

            # ── Bloquear recursos desnecessários ──────────────────────────────
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,woff,woff2,ttf,eot}",
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


# ── Fallback HTTP ─────────────────────────────────────────────────────────────

async def http_fallback(url: str, timeout: float = 15.0) -> tuple[str, int]:
    """
    Tenta obter o HTML via httpx sem browser.

    Útil quando o Playwright recebe 403 mas o site aceita requests HTTP normais.
    Devolve (html, status_code). Em caso de erro devolve ("", 0).
    """
    domain = urlparse(url).netloc
    if domain in KNOWN_BLOCKED_DOMAINS:
        logger.debug(f"[{domain}] domínio bloqueado conhecido — a saltar fallback.")
        return "", 403

    headers = {
        "User-Agent": _USER_AGENTS[0],
        **_REALISTIC_HEADERS,
        "Referer": f"https://www.google.pt/search?q={domain}",
    }

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
            http2=True,  # alguns sites bloqueiam HTTP/1.1 de bots
        ) as client:
            r = await client.get(url)
            logger.info(f"[HTTP fallback] {url} → {r.status_code}")
            if r.status_code == 200:
                return r.text, 200
            return "", r.status_code
    except httpx.TimeoutException:
        logger.warning(f"[HTTP fallback] Timeout: {url}")
        return "", 0
    except Exception as exc:
        logger.warning(f"[HTTP fallback] Erro em {url}: {exc}")
        return "", 0


def should_use_http_only(url: str) -> bool:
    """Verdadeiro para domínios configurados para usar só HTTP (sem Playwright)."""
    domain = urlparse(url).netloc
    return any(domain.endswith(d) for d in HTTP_ONLY_DOMAINS)


# ── Utilitários internos ──────────────────────────────────────────────────────

def _should_block(url: str) -> bool:
    """Bloqueia imagens e fontes mas permite SVG (necessário para logos)."""
    blocked_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp",
                          ".woff", ".woff2", ".ttf", ".eot")
    return any(url.lower().split("?")[0].endswith(ext)
               for ext in blocked_extensions)


# Script de stealth manual mínimo — usado apenas se playwright-stealth
# não estiver instalado. Cobre as verificações mais comuns.
_MANUAL_STEALTH_SCRIPT = """
() => {
    // Esconder navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true,
    });

    // Simular plugins reais (Chrome sem plugins = suspeito)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
        configurable: true,
    });

    // Simular linguagens
    Object.defineProperty(navigator, 'languages', {
        get: () => ['pt-PT', 'pt', 'en-GB', 'en'],
        configurable: true,
    });

    // Corrigir chrome.runtime (ausente em headless)
    if (!window.chrome) {
        window.chrome = { runtime: {} };
    }

    // Remover propriedade que denuncia automation
    delete window.__playwright;
    delete window.__pw_manual;
}
"""