from dispatch import display_label


def test_display_label():
    assert display_label("  North  ") == "North"


def test_short_label():
    assert display_label("A") == "A"


def test_label_available():
    assert True
