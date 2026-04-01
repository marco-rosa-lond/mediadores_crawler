"""
Navegador de páginas internas de um site de mediador.

Para cada domínio, visita a homepage e tenta as paths internas definidas
em config.INTERNAL_PATHS. Devolve o HTML renderizado (com JS executado)
de cada página encontrada.
"""
import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from config import INTERNAL_PATHS, REQUEST_TIMEOUT_MS, RETRY_ATTEMPTS

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    url: str
    html: str
    status: int
    title: str = ""
    error: str = ""
    is_homepage: bool = False


@dataclass
class SiteResult:
    base_url: str
    pages: list[PageResult] = field(default_factory=list)
    discovered_links: list[str] = field(default_factory=list)
    error: str = ""


class PageNavigator:
    """
    Navega por um site e recolhe o HTML de páginas relevantes.

    Estratégia:
    1. Carrega a homepage e aguarda que o JS renderize.
    2. Tenta cada path de INTERNAL_PATHS.
    3. Descobre links internos na homepage (descoberta heurística).
    4. Devolve SiteResult com todas as páginas encontradas.
    """

    def __init__(self, page: Page):
        self.page = page

    async def crawl_site(self, base_url: str) -> SiteResult:
        """Ponto de entrada: crawl completo de um site."""
        base_url = _normalise_url(base_url)
        result = SiteResult(base_url=base_url)

        # 1. Homepage
        homepage = await self._load_page(base_url, is_homepage=True)
        if homepage.error:
            result.error = homepage.error
            return result

        result.pages.append(homepage)

        # 2. Descobrir links internos na homepage
        discovered = await self._discover_internal_links(base_url)
        result.discovered_links = discovered

        # 3. Tentar paths predefinidas
        visited = {base_url}
        for path in INTERNAL_PATHS[1:]:  # skip "/" já visitado
            url = urljoin(base_url, path)
            if url in visited:
                continue
            visited.add(url)
            page_result = await self._load_page(url)
            if not page_result.error:
                result.pages.append(page_result)

        # 4. Tentar links descobertos heuristicamente (máx 5 extras)
        extra_count = 0
        for link in discovered:
            if extra_count >= 5:
                break
            if link in visited:
                continue
            if _is_relevant_link(link):
                visited.add(link)
                page_result = await self._load_page(link)
                if not page_result.error:
                    result.pages.append(page_result)
                    extra_count += 1

        logger.info(
            f"[{base_url}] {len(result.pages)} página(s) recolhidas."
        )
        return result

    async def _load_page(
        self, url: str, is_homepage: bool = False
    ) -> PageResult:
        """Carrega uma página e aguarda que o conteúdo dinâmico seja renderizado."""
        for attempt in range(1, RETRY_ATTEMPTS + 2):
            try:
                response = await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=REQUEST_TIMEOUT_MS,
                )
                if response is None:
                    return PageResult(url=url, html="", status=0,
                                      error="Sem resposta")

                status = response.status
                if status >= 400:
                    return PageResult(url=url, html="", status=status,
                                      error=f"HTTP {status}")

                # Aguardar renderização JS extra (simuladores, iframes)
                await self._wait_for_render()

                html = await self.page.content()
                title = await self.page.title()

                return PageResult(
                    url=url,
                    html=html,
                    status=status,
                    title=title,
                    is_homepage=is_homepage,
                )

            except PlaywrightTimeout:
                logger.warning(f"[{url}] Timeout (tentativa {attempt})")
                if attempt > RETRY_ATTEMPTS:
                    return PageResult(url=url, html="", status=0,
                                      error="Timeout")
                await asyncio.sleep(2 ** attempt)

            except Exception as exc:
                logger.warning(f"[{url}] Erro: {exc} (tentativa {attempt})")
                if attempt > RETRY_ATTEMPTS:
                    return PageResult(url=url, html="", status=0,
                                      error=str(exc))
                await asyncio.sleep(1)

        return PageResult(url=url, html="", status=0, error="Falha após retries")

    async def _wait_for_render(self) -> None:
        """
        Aguarda que o conteúdo dinâmico seja renderizado.
        Estratégia: esperar estabilidade de rede + scroll para activar lazy load.
        """
        try:
            await self.page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeout:
            pass  # Aceitar estado parcial; melhor que falhar

        # Scroll suave para activar lazy-loaded content
        await self.page.evaluate("""
            window.scrollTo({ top: document.body.scrollHeight / 2, behavior: 'smooth' });
        """)
        await asyncio.sleep(0.5)
        await self.page.evaluate("window.scrollTo({ top: 0 })")

    async def _discover_internal_links(self, base_url: str) -> list[str]:
        """Extrai links internos da página actualmente carregada."""
        try:
            domain = urlparse(base_url).netloc
            links = await self.page.evaluate(f"""
                (() => {{
                    const domain = "{domain}";
                    return Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.href)
                        .filter(href => href.includes(domain))
                        .slice(0, 50);
                }})()
            """)
            return list(dict.fromkeys(links))  # dedup preservando ordem
        except Exception:
            return []


def _normalise_url(url: str) -> str:
    """Garante que a URL tem scheme e remove trailing slash."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def _is_relevant_link(url: str) -> bool:
    """Heurística para identificar links com conteúdo relevante."""
    relevant_patterns = re.compile(
        r"/(parceiro|seguradora|simulad|seguro|produto|servico|"
        r"contacto|sobre|quem-somos|apoio|parceria)",
        re.IGNORECASE,
    )
    irrelevant_patterns = re.compile(
        r"\.(pdf|doc|docx|xls|xlsx|zip|png|jpg|jpeg|gif)$"
        r"|/(login|admin|wp-admin|cart|checkout)",
        re.IGNORECASE,
    )
    return bool(relevant_patterns.search(url)) and not bool(
        irrelevant_patterns.search(url)
    )
