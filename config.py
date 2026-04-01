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
    "Fidelidade":       ["fidelidade", "fidelidade-mundial"],
    "Tranquilidade":    ["tranquilidade"],
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
    # "Logo":             ["logo seguros", "logo"],
    "Ok!teleseguros":   ["okteleseguros", "ok teleseguros"],
    "MGEN":   ["mgen"],
    "MetLife":   ["MetLife", 'metlife'],
    "MAPFRE":   ["MAPFRE", 'mapfre'],
    "Caravela":   ["Caravela", 'caravela seguros'],
    "Una":   ["Una", 'una'],
    "prévoir":   ["prevoir"],
    "acp":   ["ACP"],
    "ARAG":   ["arag"],
    "ASSA":   ["assa"],
    "caser":   ["caser"],
    "lloyd's":   ["Lloyd's", "Lloyds"],
    "Reale":   ["reale"],
    "STARR":   ["starr"],
    "Coface":   ["coface"],
    "Cosec":   ["cosec"],
    "eurovida":   ["eurovida"],
    "Victoria":   ["victoria"],
    "Cesce":   ["cesce"],
    "SaudePrime":   ["saude_prime", "saude prime"],
    "açoreana":   ["açoreana", "acoreana"],
    "AIG":   ["aig"],
    "innovarisk":   ["innovarisk"],
}

# ── Armazenamento ─────────────────────────────────────────────────────────────
DB_PATH         = "mediadores.db"
OUTPUT_EXCEL    = "resultados_mediadores.xlsx"
RAW_OUTPUT_DIR  = "raw_pages"   # Directório para HTML raw (debug)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE  = "crawler.log"
