"""
Unit tests for email validation utilities
"""
import pytest
from app.utils.email_validation import is_plausible_email, extract_emails_from_text, format_job_error
from app.services.exceptions import RateLimitError


def test_is_plausible_email_valid():
    """Test that valid emails are accepted"""
    valid_emails = [
        "info@example.com",
        "contact@company.co.uk",
        "support@domain-name.com",
        "hello@test.io",
        "user.name@example.org",
        "user+tag@example.com",
    ]
    
    for email in valid_emails:
        assert is_plausible_email(email), f"Valid email rejected: {email}"


def test_is_plausible_email_garbage():
    """Test that garbage emails are rejected"""
    garbage_emails = [
        "acceler@ed-checkout-backwards-compat.css",
        "candy-cane-white-chocol@e-popcorn-s-150x150.jpg",
        ".maplibregl-ctrl-@trib.maplibregl-compact-show.maplibregl",
        "test@test.css",
        "email@file.js",
        "contact@image.png",
        "user@asset.svg",
        "kd@a.price",  # Very short domain
        "@domain.com",  # Missing local part
        "user@",  # Missing domain
        "user@domain",  # Missing TLD
    ]
    
    for email in garbage_emails:
        assert not is_plausible_email(email), f"Garbage email accepted: {email}"


def test_extract_emails_from_text():
    """Test email extraction from text"""
    text = """
    Contact us at info@example.com or support@company.com.
    Also try hello@test.io.
    Ignore garbage like test@file.css and image@asset.jpg.
    """
    
    emails = extract_emails_from_text(text)
    
    # Should find valid emails
    assert "info@example.com" in emails
    assert "support@company.com" in emails
    assert "hello@test.io" in emails
    
    # Should NOT find garbage
    assert "test@file.css" not in emails
    assert "image@asset.jpg" not in emails


def test_format_job_error():
    """Test error formatting for job messages"""
    # SyntaxError
    syntax_err = SyntaxError("invalid syntax", ("file.py", 10, 1, "if x:"))
    assert "syntax" in format_job_error(syntax_err).lower()
    
    # ImportError
    import_err = ImportError("No module named 'missing'")
    assert "import" in format_job_error(import_err).lower()
    
    # TimeoutError
    timeout_err = TimeoutError("Operation timed out")
    assert "timeout" in format_job_error(timeout_err).lower()
    
    # Other exception
    value_err = ValueError("Invalid value")
    assert "ValueError" in format_job_error(value_err)
    assert "Invalid value" in format_job_error(value_err)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

