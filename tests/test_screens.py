from src.screens import normalize_ticker_input


def test_normalize_ticker_input_by_country():
    assert normalize_ticker_input("KR_TOP200", "005930") == "005930.KS"
    assert normalize_ticker_input("JP_TOP200", "7203") == "7203.T"
    assert normalize_ticker_input("US_TOP500", "BRK.B") == "BRK-B"
    assert normalize_ticker_input("EU_TOP200", "ASML.AS") == "ASML.AS"
