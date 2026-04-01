"""
Configurações centrais da plataforma de análise de mediadores.
Ajuste estas constantes antes de executar o pipeline.
"""
from dataclasses import dataclass, field
from typing import List


# ── Concorrência ──────────────────────────────────────────────────────────────
MAX_WORKERS         = 10        # Browsers Playwright em simultâneo
REQUEST_TIMEOUT_MS  = 20_000   # Timeout por página (ms)
RETRY_ATTEMPTS      = 2        # Tentativas em caso de falha
RATE_LIMIT_DELAY    = 1.0      # Segundos entre pedidos ao mesmo domínio

# Sites com proteção conhecida — ignorar após 1ª tentativa
KNOWN_BLOCKED_DOMAINS = [
    # preencher com domínios que bloqueiam sistematicamente
]

# Tentar apenas HTTP simples (sem Playwright)
HTTP_ONLY_DOMAINS = [
    # sites que bloqueiam browsers headless mas aceitam requests
]

# ── Páginas internas a visitar ────────────────────────────────────────────────
INTERNAL_PATHS = [
    "/",
    "/parceiros",
    "/seguradoras",
    "/simulador",
    "/simuladores",
    "/seguros",
    "/contacto",
    "/contactos",
    "/sobre",
    "/quem-somos",
]

# ── Palavras-chave para deteção ───────────────────────────────────────────────
SIMULATOR_KEYWORDS = [
    "simulador", "simular", "simulação", "calcule", "calcular",
    "obter cotação", "peça orçamento", "orçamento online",
    "compare seguros", "seguro online", "proposta online",
]

FORM_KEYWORDS = [
    "nome", "email", "telefone", "telemóvel", "nif", "contacto",
    "enviar", "submeter", "pedir proposta",
]

PARTNER_KEYWORDS = [
    "parceiros", "seguradoras", "trabalhamos com", "protocolos",
    "companhias", "marcas que representamos",
]

# ── Lista de seguradoras em Portugal ─────────────────────────────────────────
SEGURADORAS = {
    "Allianz":          ["allianz"],
    "Fidelidade":       ["fidelidade seguros", "fidelidade-mundial"],
    "Tranquilidade":    ["tranquilidade seguros"],
    "AXA":              ["axa"],
    "Generali":         ["generali"],
    "Zurich":           ["zurich", "zürich"],
    "Ageas":            ["ageas", "ocidental"],
    "Lusitania":        ["lusitania"],
    "Liberty":          ["liberty", "liberty seguros"],
    "Groupama":         ["groupama"],
    "Hiscox":           ["hiscox"],
    "Multicare":        ["multicare"],
    "Médis":            ["médis", "medis"],
    "AdvanceCare":      ["advancecare", "advance care"],
    "Logo":             ["logo seguros"],
    "Ok!teleseguros":   ["okteleseguros", "ok teleseguros"],
    "MGEN":   ["mgen"],
    "MetLife":   ["MetLife", 'metlife'],
    "MAPFRE":   ["MAPFRE", 'mapfre'],
    "Caravela":   ["Caravela", 'caravela seguros'],
    "Una":   ['una'],
    "Prévoir":   ["prevoir"],
    "ACP":   ["ACP"],
    "ARAG":   ["arag"],
    "ASSA":   ["assa"],
    "caser":   ["caser"],
    "lloyd's":   ["Lloyd's", "Lloyds"],
    "Reale":   ["reale"],
    "STARR":   ["starr"],
    "Coface":   ["coface"],
    "Cosec":   ["cosec"],
    "EuroVida":   ["eurovida"],
    "Victoria":   ["victoria"],
    "Cesce":   ["cesce"],
    "SaudePrime":   ["saude_prime", "saude prime"],
    "Açoreana":   ["açoreana", "acoreana"],
    "AIG":   ["aig"],
    "innovarisk":   ["innovarisk"],
}

SEGURADORAS_URLS = {
    "SaudePrime": "http://www.saudeprime.pt/",
    "Liberty": "http://www.libertyseguros.pt/",
    "Lusitania": "http://www.lusitania.pt/",
    "MAPFRE": "http://www.mapfre.pt/",
    "AGEAS": "https://www.ageas.pt",
    "Prévoir": "http://www.prevoir.pt/",
    "Tranquilidade": "https://www.tranquilidade.pt/pt",
    "Fidelidade": "https://www.fidelidade.pt",
    "Allianz": "http://www.allianz.pt/",
    "Zurich": "http://www.zurich.com/portugal/home/home.htm",
    "Generali": "http://www.generali.pt/",
    "Caravela": "https://www.caravelaseguros.pt/",
    "Logo": "https://www.logo.pt",
    # "april": "https://www.april-portugal.pt/",
    # "ergo": "https://www.ergo-segurosdeviagem.pt/",
    # "realvida": "https://www.realvidaseguros.pt/"
}

# ── Armazenamento ─────────────────────────────────────────────────────────────
DB_PATH         = "mediadores.db"
OUTPUT_EXCEL    = "resultados_mediadores.xlsx"
RAW_OUTPUT_DIR  = "raw_pages"   # Directório para HTML raw (debug)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE  = "crawler.log"
