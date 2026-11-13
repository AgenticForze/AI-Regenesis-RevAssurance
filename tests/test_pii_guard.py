import pii_guard


def test_blocks_card_number():
    assert "card_number" in pii_guard.find_pii("card 4111 1111 1111 1111")


def test_allows_example_email():
    assert pii_guard.find_pii("contact owner@example.com") == []


def test_blocks_real_looking_email():
    assert "email" in pii_guard.find_pii("send to jane.doe@corp-mail.net")
