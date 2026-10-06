from packages.email import (
    extract_sender_domain,
    normalize_company_name,
    normalize_domain,
    normalize_job_title,
)


def test_company_normalization_removes_legal_suffixes() -> None:
    assert normalize_company_name("Roland Berger GmbH") == "roland berger"
    assert normalize_company_name("Example, Inc.") == "example"


def test_title_and_domain_normalization_are_stable() -> None:
    assert normalize_job_title("Senior AI-Engineer") == "senior ai engineer"
    assert normalize_domain("WWW.Example.COM.") == "example.com"
    assert extract_sender_domain("person@example.com") == "example.com"
    assert extract_sender_domain("person@gmail.com") is None

