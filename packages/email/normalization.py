import re

_COMPANY_SUFFIXES = {
    "ag",
    "corp",
    "corporation",
    "gmbh",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "plc",
}
_GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "icloud.com",
    "outlook.com",
    "yahoo.com",
}


def _normalize_words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def normalize_company_name(value: str) -> str:
    words = _normalize_words(value)
    while words and words[-1] in _COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


def normalize_job_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(_normalize_words(value))
    return normalized or None


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    domain = value.strip().casefold().rstrip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None


def extract_sender_domain(sender: str) -> str | None:
    _, separator, domain = sender.rpartition("@")
    if not separator:
        return None
    normalized = normalize_domain(domain)
    if normalized in _GENERIC_EMAIL_DOMAINS:
        return None
    return normalized

