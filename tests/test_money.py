"""Money conversion, splitting and rendering. Everything here is exact by construction."""

from server.domain.money import allocate, format_rupees, from_rupees, speak_rupees


def test_rupees_convert_to_paise():
    assert from_rupees(18_000) == 1_800_000
    assert from_rupees("8500.50") == 850_050
    assert from_rupees(0) == 0


def test_binary_float_error_does_not_reach_paise():
    # 0.1 + 0.2 is 0.30000000000000004 as a float. Round-tripping through str()
    # is what keeps that out of the ledger.
    assert from_rupees(0.1 + 0.2) == 30
    assert from_rupees(1234.565) == 123_457  # half-up, not banker's rounding


def test_allocate_loses_nothing():
    total = from_rupees(11_000)  # does not divide by 30
    parts = allocate(total, 30)
    assert sum(parts) == total
    assert len(parts) == 30
    assert max(parts) - min(parts) == 1  # remainder spread a paisa at a time


def test_allocate_handles_negatives_and_exact_splits():
    assert sum(allocate(-1_100_000, 30)) == -1_100_000
    assert allocate(from_rupees(3_000), 30) == [10_000] * 30


def test_indian_digit_grouping():
    assert format_rupees(from_rupees(1_000)) == "1,000"
    assert format_rupees(from_rupees(150_000)) == "1,50,000"
    assert format_rupees(from_rupees(1_23_45_678)) == "1,23,45,678"
    assert format_rupees(from_rupees("99.50")) == "99.50"
    assert format_rupees(from_rupees(-8_000)) == "-8,000"


def test_amounts_are_spoken_as_words():
    # The rupee symbol and long digit strings are exactly what TTS gets wrong.
    assert speak_rupees(from_rupees(18_000)) == "eighteen thousand rupees"
    assert speak_rupees(from_rupees(4_200)) == "four thousand two hundred rupees"
    assert speak_rupees(from_rupees(150_000)) == "one lakh fifty thousand rupees"
    assert speak_rupees(from_rupees(1)) == "one rupee"
    assert "₹" not in speak_rupees(from_rupees(9_500))
