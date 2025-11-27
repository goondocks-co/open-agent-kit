"""Tests for open-agent-kit data models."""

from open_agent_kit.models.rfc import RFCDocument, RFCIndex, RFCStatus


def test_rfc_status_enum() -> None:
    """Test RFC status enumeration values."""
    assert RFCStatus.DRAFT.value == "draft"
    assert RFCStatus.REVIEW.value == "review"
    assert RFCStatus.APPROVED.value == "approved"
    assert RFCStatus.ADOPTED.value == "adopted"
    assert RFCStatus.ABANDONED.value == "abandoned"
    assert RFCStatus.IMPLEMENTED.value == "implemented"
    assert RFCStatus.WONT_IMPLEMENT.value == "wont-implement"


def test_rfc_document_creation() -> None:
    """Test creating an RFC document."""
    rfc = RFCDocument(
        number="001",
        title="Test RFC",
        author="Test Author",
        date="2025-11-04",
        status=RFCStatus.DRAFT,
        tags=["test", "automation"],
    )
    assert rfc.number == "001"
    assert rfc.title == "Test RFC"
    assert rfc.author == "Test Author"
    assert rfc.status == RFCStatus.DRAFT
    assert rfc.tags == ["test", "automation"]


def test_rfc_document_is_active() -> None:
    """Test RFC is_active property."""
    draft_rfc = RFCDocument(
        number="001", title="Draft RFC", author="Author", date="2025-11-04", status=RFCStatus.DRAFT
    )
    review_rfc = RFCDocument(
        number="002",
        title="Review RFC",
        author="Author",
        date="2025-11-04",
        status=RFCStatus.REVIEW,
    )
    approved_rfc = RFCDocument(
        number="003",
        title="Approved RFC",
        author="Author",
        date="2025-11-04",
        status=RFCStatus.APPROVED,
    )
    implemented_rfc = RFCDocument(
        number="004",
        title="Implemented RFC",
        author="Author",
        date="2025-11-04",
        status=RFCStatus.IMPLEMENTED,
    )
    assert draft_rfc.is_active
    assert review_rfc.is_active
    assert approved_rfc.is_active
    assert not implemented_rfc.is_active


def test_rfc_document_is_final() -> None:
    """Test RFC is_final property."""
    draft_rfc = RFCDocument(
        number="001", title="Draft RFC", author="Author", date="2025-11-04", status=RFCStatus.DRAFT
    )
    adopted_rfc = RFCDocument(
        number="002",
        title="Adopted RFC",
        author="Author",
        date="2025-11-04",
        status=RFCStatus.ADOPTED,
    )
    implemented_rfc = RFCDocument(
        number="003",
        title="Implemented RFC",
        author="Author",
        date="2025-11-04",
        status=RFCStatus.IMPLEMENTED,
    )
    assert not draft_rfc.is_final
    assert adopted_rfc.is_final
    assert implemented_rfc.is_final


def test_rfc_document_to_dict() -> None:
    """Test RFC serialization to dictionary."""
    rfc = RFCDocument(
        number="001",
        title="Test RFC",
        author="Test Author",
        date="2025-11-04",
        status=RFCStatus.DRAFT,
        tags=["test"],
    )
    data = rfc.to_dict()
    assert data["number"] == "001"
    assert data["title"] == "Test RFC"
    assert data["author"] == "Test Author"
    assert data["status"] == "draft"
    assert data["tags"] == ["test"]


def test_rfc_document_from_dict() -> None:
    """Test RFC deserialization from dictionary."""
    data = {
        "number": "001",
        "title": "Test RFC",
        "author": "Test Author",
        "date": "2025-11-04",
        "status": "draft",
        "tags": ["test"],
    }
    rfc = RFCDocument.from_dict(data)
    assert rfc.number == "001"
    assert rfc.title == "Test RFC"
    assert rfc.author == "Test Author"
    assert rfc.status == RFCStatus.DRAFT
    assert rfc.tags == ["test"]


def test_rfc_index_add_rfc() -> None:
    """Test adding RFC to index."""
    index = RFCIndex()
    rfc = RFCDocument(number="001", title="Test RFC", author="Author", date="2025-11-04")
    index.add_rfc(rfc)
    assert index.total_count == 1
    assert index.get_rfc("001") == rfc


def test_rfc_index_statistics() -> None:
    """Test RFC index statistics."""
    index = RFCIndex()
    index.add_rfc(
        RFCDocument(
            number="001",
            title="Draft RFC",
            author="Author",
            date="2025-11-04",
            status=RFCStatus.DRAFT,
        )
    )
    index.add_rfc(
        RFCDocument(
            number="002",
            title="Review RFC",
            author="Author",
            date="2025-11-04",
            status=RFCStatus.REVIEW,
        )
    )
    index.add_rfc(
        RFCDocument(
            number="003",
            title="Another Draft",
            author="Author",
            date="2025-11-04",
            status=RFCStatus.DRAFT,
        )
    )
    assert index.total_count == 3
    assert index.by_status["draft"] == 2
    assert index.by_status["review"] == 1


def test_rfc_index_search_by_status() -> None:
    """Test searching RFCs by status."""
    index = RFCIndex()
    draft_rfc = RFCDocument(
        number="001", title="Draft", author="Author", date="2025-11-04", status=RFCStatus.DRAFT
    )
    review_rfc = RFCDocument(
        number="002", title="Review", author="Author", date="2025-11-04", status=RFCStatus.REVIEW
    )
    index.add_rfc(draft_rfc)
    index.add_rfc(review_rfc)
    draft_results = index.search(status=RFCStatus.DRAFT)
    assert len(draft_results) == 1
    assert draft_results[0].number == "001"


def test_rfc_index_search_by_author() -> None:
    """Test searching RFCs by author."""
    index = RFCIndex()
    rfc1 = RFCDocument(number="001", title="RFC 1", author="Alice", date="2025-11-04")
    rfc2 = RFCDocument(number="002", title="RFC 2", author="Bob", date="2025-11-04")
    rfc3 = RFCDocument(number="003", title="RFC 3", author="Alice", date="2025-11-04")
    index.add_rfc(rfc1)
    index.add_rfc(rfc2)
    index.add_rfc(rfc3)
    alice_rfcs = index.search(author="Alice")
    assert len(alice_rfcs) == 2
    assert all(rfc.author == "Alice" for rfc in alice_rfcs)


def test_rfc_get_next_number() -> None:
    """Test RFC next number generation."""
    index = RFCIndex()
    next_num = index.get_next_number(format="sequential")
    assert next_num == "1"
    index.add_rfc(RFCDocument(number="001", title="First", author="Author", date="2025-11-04"))
    next_num = index.get_next_number(format="sequential")
    assert next_num == "2"
