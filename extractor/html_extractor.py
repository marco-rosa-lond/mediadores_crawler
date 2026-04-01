"""
Extractor de conteúdo HTML.

Recebe o HTML renderizado de uma página e extrai:
- Texto visível limpo
- Formulários (campos, action, method)
- Iframes (src, título)
- Presença de palavras-chave (simuladores, formulários, parceiros)
- Seguradoras mencionadas por texto
- Score de confiança para cada tipo de deteção
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

from config import (
    SIMULATOR_KEYWORDS,
    FORM_KEYWORDS,
    PARTNER_KEYWORDS,
    SEGURADORAS,
)

logger = logging.getLogger(__name__)


# ── Estruturas de dados ───────────────────────────────────────────────────────

@dataclass
class FormInfo:
    action: str
    method: str
    fields: list[str]           # nomes/tipos dos inputs
    has_email: bool = False
    has_phone: bool = False
    is_simulation_form: bool = False


@dataclass
class IframeInfo:
    src: str
    title: str
    is_simulator: bool = False


@dataclass
class ExtractionResult:
    url: str
    title: str
    text: str                               # Texto limpo
    forms: list[FormInfo] = field(default_factory=list)
    iframes: list[IframeInfo] = field(default_factory=list)
    seguradoras_texto: dict[str, float] = field(default_factory=dict)  # nome → score
    has_simulator: bool = False
    simulator_score: float = 0.0           # 0.0–1.0
    has_contact_form: bool = False
    contact_form_score: float = 0.0
    has_partners_section: bool = False
    partner_keywords_found: list[str] = field(default_factory=list)
    simulator_keywords_found: list[str] = field(default_factory=list)
    raw_links: list[str] = field(default_factory=list)


# ── Extractor principal ───────────────────────────────────────────────────────

class HTMLExtractor:
    """
    Extrai informação estruturada de HTML renderizado.

    Uso:
        extractor = HTMLExtractor()
        result = extractor.extract(html, url="https://mediador.pt", title="...")
    """

    def __init__(self):
        self._sim_re = _build_keyword_re(SIMULATOR_KEYWORDS)
        self._form_re = _build_keyword_re(FORM_KEYWORDS)
        self._partner_re = _build_keyword_re(PARTNER_KEYWORDS)
        self._seguradora_patterns = {
            name: re.compile(
                r"\b(" + "|".join(re.escape(a) for a in aliases) + r")\b",
                re.IGNORECASE,
            )
            for name, aliases in SEGURADORAS.items()
        }

    def extract(self, html: str, url: str = "", title: str = "") -> ExtractionResult:
        if not html:
            return ExtractionResult(url=url, title=title, text="")

        soup = BeautifulSoup(html, "lxml")
        _remove_noise(soup)

        text = _extract_visible_text(soup)
        text_lower = text.lower()

        result = ExtractionResult(url=url, title=title, text=text)

        # Formulários
        result.forms = self._extract_forms(soup, text_lower)

        # Iframes
        result.iframes = self._extract_iframes(soup)

        # Links
        result.raw_links = [
            a.get("href", "") for a in soup.find_all("a", href=True)
        ][:100]

        # Seguradoras por texto
        result.seguradoras_texto = self._detect_seguradoras(text)

        # Scores de simulador
        sim_kws = _find_keywords(text_lower, SIMULATOR_KEYWORDS)
        result.simulator_keywords_found = sim_kws
        result.has_simulator, result.simulator_score = self._score_simulator(
            sim_kws, result.iframes, result.forms
        )

        # Score de formulário de contacto
        form_kws = _find_keywords(text_lower, FORM_KEYWORDS)
        result.has_contact_form, result.contact_form_score = self._score_contact_form(
            result.forms, form_kws
        )

        # Parceiros
        partner_kws = _find_keywords(text_lower, PARTNER_KEYWORDS)
        result.partner_keywords_found = partner_kws
        result.has_partners_section = len(partner_kws) > 0

        return result

    # ── Extração de formulários ───────────────────────────────────────────────

    def _extract_forms(self, soup: BeautifulSoup, text_lower: str) -> list[FormInfo]:
        forms = []
        for form_tag in soup.find_all("form"):
            fields = []
            has_email = False
            has_phone = False

            for inp in form_tag.find_all(["input", "select", "textarea"]):
                inp_type = inp.get("type", "text").lower()
                inp_name = inp.get("name", inp.get("id", inp_type))
                fields.append(f"{inp_name}:{inp_type}")

                name_lower = inp_name.lower()
                if inp_type == "email" or "email" in name_lower:
                    has_email = True
                if inp_type == "tel" or any(
                    k in name_lower for k in ("telefone", "telemovel", "phone", "tel")
                ):
                    has_phone = True

            form_text = form_tag.get_text(" ", strip=True).lower()
            is_sim = bool(self._sim_re.search(form_text))

            forms.append(FormInfo(
                action=form_tag.get("action", ""),
                method=form_tag.get("method", "get").upper(),
                fields=fields,
                has_email=has_email,
                has_phone=has_phone,
                is_simulation_form=is_sim,
            ))
        return forms

    # ── Extração de iframes ───────────────────────────────────────────────────

    def _extract_iframes(self, soup: BeautifulSoup) -> list[IframeInfo]:
        iframes = []
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            title = iframe.get("title", iframe.get("name", ""))
            is_sim = bool(self._sim_re.search((src + " " + title).lower()))
            iframes.append(IframeInfo(src=src, title=title, is_simulator=is_sim))
        return iframes

    # ── Deteção de seguradoras ────────────────────────────────────────────────

    def _detect_seguradoras(self, text: str) -> dict[str, float]:
        found = {}
        for name, pattern in self._seguradora_patterns.items():
            matches = pattern.findall(text)
            if matches:
                # Score baseado em frequência (normalizado 0–1)
                score = min(1.0, len(matches) / 3)
                found[name] = round(score, 2)
        return found

    # ── Scores ────────────────────────────────────────────────────────────────

    def _score_simulator(
        self,
        keywords: list[str],
        iframes: list[IframeInfo],
        forms: list[FormInfo],
    ) -> tuple[bool, float]:
        score = 0.0
        score += min(0.4, len(keywords) * 0.1)           # keywords no texto
        score += sum(0.3 for i in iframes if i.is_simulator)
        score += sum(0.2 for f in forms if f.is_simulation_form)
        score = min(1.0, score)
        return score >= 0.2, round(score, 2)

    def _score_contact_form(
        self, forms: list[FormInfo], keywords: list[str]
    ) -> tuple[bool, float]:
        score = 0.0
        for f in forms:
            if f.has_email:
                score += 0.4
            if f.has_phone:
                score += 0.3
            if len(f.fields) >= 3:
                score += 0.2
        score += min(0.2, len(keywords) * 0.05)
        score = min(1.0, score)
        return score >= 0.3, round(score, 2)


# ── Utilitários ───────────────────────────────────────────────────────────────

def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove tags que não contribuem para o conteúdo visível."""
    for tag in soup(["script", "style", "noscript", "meta",
                     "head", "footer", "nav"]):
        tag.decompose()


def _extract_visible_text(soup: BeautifulSoup) -> str:
    """Extrai e normaliza o texto visível."""
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_keyword_re(keywords: list[str]) -> re.Pattern:
    pattern = "|".join(re.escape(k) for k in keywords)
    return re.compile(pattern, re.IGNORECASE)


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    found = []
    for kw in keywords:
        if kw.lower() in text:
            found.append(kw)
    return found
