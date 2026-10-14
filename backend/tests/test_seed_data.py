from app.seed_data import SEED_LEADS


def test_sample_data_meets_minimum_requirements():
    with_chat = [lead for lead in SEED_LEADS if lead.messages]
    assert len(SEED_LEADS) >= 20
    assert len(with_chat) >= 10
    assert any(not lead.messages for lead in SEED_LEADS)
    assert len({lead.phone for lead in SEED_LEADS}) == len(SEED_LEADS)
    for lead in with_chat:
        assert 3 <= len(lead.messages) <= 9, lead.key


def test_chats_never_put_a_message_in_the_future():
    # A message "0 days ago" at a fixed clock time could land after the moment of seeding.
    for lead in SEED_LEADS:
        assert all(m.days_ago >= 1 for m in lead.messages), lead.key
        assert lead.created_days_ago >= max((m.days_ago for m in lead.messages), default=0)


def test_messages_are_listed_oldest_first():
    for lead in SEED_LEADS:
        stamps = [(-m.days_ago, m.time) for m in lead.messages]
        assert stamps == sorted(stamps), lead.key
