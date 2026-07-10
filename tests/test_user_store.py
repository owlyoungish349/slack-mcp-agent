from store import user_store


def test_impact_dashboard_counts_people_not_repeat_welcome_or_match_events(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(user_store, "_DATA_DIR", tmp_path)
    user_store.init_db()

    user_store.log_event("welcomed", "U1")
    user_store.log_event("welcomed", "U1")
    user_store.log_event("matched", "U1")
    user_store.log_event("matched", "U1")
    user_store.log_event("intro_made", "U1")
    user_store.log_event("intro_made", "U1")
    user_store.log_event("digest_sent", "U1")
    user_store.log_event("digest_sent", "U1")

    summary = user_store.get_impact_summary()

    assert summary["welcomed"] == 1
    assert summary["matched"] == 1
    assert summary["intro_made"] == 2
    assert summary["digest_sent"] == 2
