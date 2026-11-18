from screening.llm.gateway import Gateway
from screening.llm.tagging import parse
from screening.text import Deduper, hamming, simhash


def test_a_lightly_edited_copy_is_one_story_and_a_different_story_is_not(world):
    caught = merged = 0
    pairs = world.duplicate_pairs("en", 200)
    for a, b, same in pairs:
        d = Deduper(11, 1)
        d.seen(a.id, a.text)
        hit = d.seen(b.id, b.text) is not None
        caught += hit and same
        merged += hit and not same
    copies = sum(1 for *_, s in pairs if s)
    assert caught / copies > 0.85
    assert merged / (len(pairs) - copies) < 0.02


def test_simhash_is_stable_and_close_for_close_texts():
    a = "the plant reported a spill near the river on monday"
    assert simhash(a, 1) == simhash(a, 1)
    near = hamming(simhash(a, 1), simhash(a + " morning", 1))
    assert near < hamming(simhash(a, 1), simhash("quarterly profit rose", 1))


def test_only_answers_in_the_schema_count():
    assert parse('{"topics": ["labour", "environment"]}') == ["environment", "labour"]
    assert parse('{"topics": []}') == []
    for bad in (None, "", "Topics: LABOUR", '{"topics": ["Labour"]}', '{"topics": "labour"}', '["labour"]',
                '{"topics": ["weather"]}'):
        assert parse(bad) is None


def test_the_gateway_checks_group_deployment_quota_and_budget():
    gw = Gateway({"sg-dev": {"deployments": ["sandbox"], "tokens_per_minute": 1000, "monthly_budget_eur": 1.0},
                  "sg-prod": {"deployments": ["screening-tagger"], "tokens_per_minute": 0, "monthly_budget_eur": 0}},
                 eur_per_1k_tokens=0.5)
    assert not gw.check(["sg-dev"], "screening-tagger", 10, 0).allowed
    v = gw.check(["sg-dev"], "sandbox", 900, 0)
    assert v.allowed
    gw.account(v.reason, 900, 0)
    assert "tokens per minute" in gw.check(["sg-dev"], "sandbox", 200, 0).reason
    assert gw.check(["sg-dev"], "sandbox", 200, 1).allowed
    gw.account("sg-dev", 1200, 2)
    assert "budget" in gw.check(["sg-dev"], "sandbox", 100, 3).reason
    assert gw.check(["sg-prod"], "screening-tagger", 10**6, 0).allowed
