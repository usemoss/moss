"""Tests for DefaultContextFormatter."""

from unittest.mock import MagicMock

from gemma_moss.formatters import DefaultContextFormatter


class TestDefaultContextFormatter:
    """Tests for DefaultContextFormatter."""

    def test_returns_none_for_empty_list(self):
        """Return None when given an empty document list."""
        formatter = DefaultContextFormatter()
        assert formatter([]) is None

    def test_formats_single_document(self):
        """Format a single document with text only."""
        doc = MagicMock()
        doc.text = "How to track your order"
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter()
        result = formatter([doc])

        assert result is not None
        assert "1. How to track your order" in result
        assert result.startswith("Relevant context from knowledge base:")

    def test_formats_multiple_documents_with_metadata(self):
        """Format multiple documents with source and score metadata."""
        doc1 = MagicMock()
        doc1.text = "Return policy info"
        doc1.metadata = {"source": "faq.md"}
        doc1.score = 0.95

        doc2 = MagicMock()
        doc2.text = "Shipping details"
        doc2.metadata = {"source": "shipping.md"}
        doc2.score = 0.87

        formatter = DefaultContextFormatter()
        result = formatter([doc1, doc2])

        assert result is not None
        assert "1. Return policy info" in result
        assert "source=faq.md" in result
        assert "score=0.95" in result
        assert "2. Shipping details" in result

    def test_custom_prefix(self):
        """Use a custom prefix."""
        doc = MagicMock()
        doc.text = "Test document"
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter(prefix="Custom prefix:\n\n")
        result = formatter([doc])

        assert result is not None
        assert result.startswith("Custom prefix:")

    def test_handles_missing_text(self):
        """Handle document with None text gracefully."""
        doc = MagicMock()
        doc.text = None
        doc.metadata = {}
        doc.score = None

        formatter = DefaultContextFormatter()
        result = formatter([doc])

        assert result is not None
        assert "1. " in result
