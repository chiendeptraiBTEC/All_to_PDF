from html.parser import HTMLParser
from pathlib import Path


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.inline_scripts = 0
        self.inline_styles = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if element_id := attributes.get("id"):
            self.ids.append(element_id)
        if tag == "script" and "src" not in attributes:
            self.inline_scripts += 1
        if tag == "style":
            self.inline_styles += 1


def test_frontend_has_unique_ids_and_no_inline_code() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    parser = IdCollector()
    parser.feed(html)

    assert len(parser.ids) == len(set(parser.ids))
    assert parser.inline_scripts == 0
    assert parser.inline_styles == 0
    assert 'lang="vi"' in html
    assert 'id="workspace"' in html


def test_frontend_does_not_collect_raw_provider_secrets() -> None:
    html = Path("frontend/index.html").read_text(encoding="utf-8").lower()

    assert 'type="password"' not in html
    assert 'name="api_key"' not in html
    assert 'id="api-key"' not in html
    assert 'id="llm-profile-id"' in html


def test_visual_language_avoids_generic_ai_gradient_ui() -> None:
    css = Path("frontend/styles.css").read_text(encoding="utf-8").lower()

    assert "linear-gradient" not in css
    assert "radial-gradient" not in css
    assert "backdrop-filter" not in css
