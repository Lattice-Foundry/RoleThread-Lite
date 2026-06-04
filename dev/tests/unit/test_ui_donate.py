from pathlib import Path

import ui.ui_donate as ui_donate


class FakeComponents:
    def __init__(self):
        self.iframe_calls = []

    def iframe(self, **kwargs):
        self.iframe_calls.append(kwargs)


class FakeStreamlit:
    def __init__(self):
        self.subheaders = []
        self.markdown_calls = []
        self.info_calls = []
        self.link_button_calls = []

    def subheader(self, text):
        self.subheaders.append(text)

    def markdown(self, text):
        self.markdown_calls.append(text)

    def info(self, text):
        self.info_calls.append(text)

    def link_button(self, label, url, **kwargs):
        self.link_button_calls.append(
            {
                "label": label,
                "url": url,
                **kwargs,
            }
        )


def test_support_rolethread_page_embeds_latticefoundry_donation_route(monkeypatch):
    fake_st = FakeStreamlit()
    fake_components = FakeComponents()
    monkeypatch.setattr(ui_donate, "st", fake_st)
    monkeypatch.setattr(ui_donate, "components", fake_components)

    ui_donate.render_support_rolethread_page()

    assert fake_st.subheaders == ["Support RoleThread"]
    assert any(
        "does not process, store, or retain payment information" in text
        for text in fake_st.markdown_calls
    )
    assert any("internet connection" in text for text in fake_st.info_calls)
    assert fake_st.link_button_calls == [
        {
            "label": "Open full donation page",
            "url": ui_donate.DONATION_FALLBACK_URL,
            "icon": ":material/open_in_new:",
        }
    ]
    assert fake_components.iframe_calls == [
        {
            "src": ui_donate.DONATION_EMBED_URL,
            "height": ui_donate.DONATION_IFRAME_HEIGHT,
            "scrolling": True,
        }
    ]


def test_donation_urls_keep_embed_and_full_page_boundaries():
    assert ui_donate.DONATION_EMBED_URL == (
        "https://latticefoundry.dev/donate/embed?"
        "source=rolethread-lite&interest=rolethread"
    )
    assert ui_donate.DONATION_FALLBACK_URL == (
        "https://latticefoundry.dev/donate?"
        "source=rolethread-lite&interest=rolethread"
    )
    assert "/donate/embed?" in ui_donate.DONATION_EMBED_URL
    assert "/donate?" in ui_donate.DONATION_FALLBACK_URL


def test_rolethread_does_not_add_payment_or_cloud_dependencies():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").casefold()
    forbidden_dependencies = (
        "stripe",
        "boto3",
        "botocore",
        "@aws-sdk",
        "dynamodb",
    )

    assert all(dependency not in requirements for dependency in forbidden_dependencies)
