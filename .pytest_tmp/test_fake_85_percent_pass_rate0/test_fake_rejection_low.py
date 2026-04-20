
def test_rejection_pass_rate_low():
    """Fake test: 17/20 pass = 85% < 90% threshold."""
    rate = 17 / 20  # 0.85
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} (17/20) < 90% threshold."
    )
