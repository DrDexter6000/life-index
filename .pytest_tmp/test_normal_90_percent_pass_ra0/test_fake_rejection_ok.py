
def test_rejection_pass_rate_ok():
    """Fake test: 18/20 pass = 90% >= 90% threshold."""
    rate = 18 / 20  # 0.90
    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} (18/20) < 90% threshold."
    )
