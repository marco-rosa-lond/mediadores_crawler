"""
Pipeline principal: orquestra crawler + extractor + persistência.

Para 500–2000 sites usa asyncio com BrowserPool de N workers paralelos.
Cada URL é processada de forma independente; erros num site não afectam os outros.

Uso:
    python pipeline.py --urls mediadores.csv --workers 10
    python pipeline.py --urls mediadores.csv --workers 20 --headless
"""
import asyncio
import csv
import logging
import sys
import time
from pathlib import Path

from crawler.browser_pool import BrowserPool
from crawler.page_navigator import PageNavigator
from extractor.html_extractor import HTMLExtractor
from storage.db import (
    init_db, upsert_mediador, insert_page,
    insert_seguradoras, insert_detection, export_to_excel,
)
from config import MAX_WORKERS, DB_PATH, OUTPUT_EXCEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("crawler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")

extractor = HTMLExtractor()  # stateless; partilhado entre workers


async def process_site(url: str, pool: BrowserPool) -> dict:
    """Crawl + extracção completa de um único site."""
    logger.info(f"→ A processar: {url}")
    t0 = time.time()

    async with pool.acquire() as page:
        navigator = PageNavigator(page)
        site_result = await navigator.crawl_site(url)

    if site_result.error:
        logger.warning(f"✗ {url}: {site_result.error}")
        return {
            "base_url": url, "nome": None,
            "has_simulator": False, "simulator_score": 0.0,
            "has_contact_form": False, "contact_form_score": 0.0,
            "has_partners": False, "seguradoras_count": 0,
            "pages_crawled": 0, "status": "error",
            "error_msg": site_result.error,
        }

    # Agrega resultados de todas as páginas
    all_seguradoras: dict[str, float] = {}
    max_simulator_score = 0.0
    max_contact_score = 0.0
    has_partners = False
    pages_data = []

    for page_r in site_result.pages:
        if not page_r.html:
            continue
        ex = extractor.extract(page_r.html, url=page_r.url, title=page_r.title)

        # Agregar seguradoras (max score por seguradora)
        for seg, score in ex.seguradoras_texto.items():
            all_seguradoras[seg] = max(all_seguradoras.get(seg, 0), score)

        max_simulator_score = max(max_simulator_score, ex.simulator_score)
        max_contact_score = max(max_contact_score, ex.contact_form_score)
        has_partners = has_partners or ex.has_partners_section

        pages_data.append({
            "url": page_r.url,
            "title": page_r.title,
            "http_status": page_r.status,
            "text": ex.text,
            "simulator_keywords": ex.simulator_keywords_found,
            "iframes": ex.iframes,
            "forms": ex.forms,
        })

    elapsed = round(time.time() - t0, 1)
    logger.info(
        f"✓ {url} — {len(pages_data)} pág | "
        f"sim={max_simulator_score:.2f} | "
        f"form={max_contact_score:.2f} | "
        f"segs={len(all_seguradoras)} | {elapsed}s"
    )

    return {
        "base_url": url,
        "nome": None,
        "has_simulator": max_simulator_score >= 0.2,
        "simulator_score": max_simulator_score,
        "has_contact_form": max_contact_score >= 0.3,
        "contact_form_score": max_contact_score,
        "has_partners": has_partners,
        "seguradoras_count": len(all_seguradoras),
        "pages_crawled": len(pages_data),
        "status": "ok",
        "error_msg": None,
        # extras para persistência
        "_pages": pages_data,
        "_seguradoras": all_seguradoras,
    }


def persist_result(result: dict) -> None:
    """Guarda o resultado de um site na BD."""
    mediador_data = {k: v for k, v in result.items() if not k.startswith("_")}
    mediador_id = upsert_mediador(mediador_data)

    for page in result.get("_pages", []):
        insert_page(mediador_id, page)
        # Registar deteções de simuladores
        if page.get("simulator_keywords") or page.get("iframes"):
            insert_detection(
                mediador_id, "simulator",
                result["simulator_score"],
                {
                    "keywords": page["simulator_keywords"],
                    "iframes": [i.src for i in page.get("iframes", [])],
                },
                page_url=page["url"],
            )

    seguradoras = result.get("_seguradoras", {})
    if seguradoras:
        insert_seguradoras(mediador_id, seguradoras, fonte="texto")


async def run_pipeline(
    urls: list[str],
    workers: int = MAX_WORKERS,
    headless: bool = True,
) -> None:
    """Executa o pipeline completo para uma lista de URLs."""
    logger.info(f"Pipeline iniciado: {len(urls)} sites | {workers} workers")
    init_db()

    async with BrowserPool(size=workers, headless=headless) as pool:
        # Semaphore extra para controlar burst (além do pool)
        sem = asyncio.Semaphore(workers)

        async def bounded(url: str):
            async with sem:
                result = await process_site(url, pool)
                persist_result(result)

        tasks = [bounded(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Pipeline concluído. A exportar para Excel...")
    export_to_excel()
    logger.info(f"Ficheiro gerado: {OUTPUT_EXCEL}")


def load_urls_from_csv(path: str) -> list[str]:
    """Carrega URLs de um CSV. Aceita ficheiros com ou sem cabeçalho."""
    urls = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                candidate = row[4].strip()
                if candidate and not candidate.lower().startswith("url"):
                    urls.append(candidate)
    return urls


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawler de mediadores de seguros")
    parser.add_argument("--urls", required=True, help="CSV com URLs (uma por linha)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help=f"Número de browsers paralelos (default: {MAX_WORKERS})")
    parser.add_argument("--no-headless", action="store_true",
                        help="Mostrar browser (debug)")
    args = parser.parse_args()

    urls = load_urls_from_csv(args.urls)
    if not urls:
        logger.error("Nenhuma URL encontrada no CSV.")
        sys.exit(1)

    logger.info(f"{len(urls)} URLs carregadas de '{args.urls}'")
    asyncio.run(run_pipeline(urls, workers=args.workers,
                             headless=not args.no_headless))


#  python pipeline.py --urls mediadores.csv --workers 15