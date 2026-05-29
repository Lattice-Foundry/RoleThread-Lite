import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
HELP_MANIFEST = REPO_ROOT / "docs" / "help_manifest.json"


def test_external_consumer_can_build_help_sidebar_from_manifest_json_only():
    manifest = json.loads(HELP_MANIFEST.read_text(encoding="utf-8"))
    categories = sorted(manifest["categories"], key=lambda record: record["order"])
    articles = manifest["articles"]
    category_ids = {category["id"] for category in categories}
    article_ids = {article["id"] for article in articles}

    assert manifest["default_article_id"] in article_ids
    assert category_ids
    assert article_ids

    sidebar = []
    for category in categories:
        category_articles = sorted(
            (
                article
                for article in articles
                if article["category"] == category["id"]
            ),
            key=lambda record: record["order"],
        )
        assert category_articles
        sidebar.append((
            category["title"],
            [article["title"] for article in category_articles],
        ))

    assert sidebar[0][0] == "Getting Started"
    assert sidebar[0][1][0] == "Installing RoleThread Lite"
    assert sidebar[-1][0] == "For Developers"
    assert sidebar[-1][1][-1] == "Lite vs Studio Boundaries"

    public_sidebar = [
        (
            category["title"],
            [
                article["title"]
                for article in sorted(
                    (
                        article
                        for article in articles
                        if article["category"] == category["id"]
                        and article["public"] is True
                    ),
                    key=lambda record: record["order"],
                )
            ],
        )
        for category in categories
    ]
    assert public_sidebar == sidebar

    for article in articles:
        source_path = Path(article["source_path"])
        assert article["category"] in category_ids
        assert set(article["related_ids"]) <= article_ids
        assert article["title"]
        assert article["summary"]
        assert article["audience"]
        assert isinstance(article["public"], bool)
        assert isinstance(article["order"], int)
        assert not source_path.is_absolute()
        assert ".." not in source_path.parts
        assert article["source_path"].startswith("docs/help/")
        assert (REPO_ROOT / source_path).is_file()
