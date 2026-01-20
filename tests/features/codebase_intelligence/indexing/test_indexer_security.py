"""Security tests for the code indexer.

This module tests critical security features of the indexer:
- Path traversal protection via symlink detection
- Sensitive file blocking
- .gitignore pattern enforcement
- Project root boundary validation

These tests ensure the indexer cannot be exploited to access or index
files outside the project scope or files containing sensitive data.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.indexing.indexer import (
    SENSITIVE_FILE_PATTERNS,
    CodebaseIndexer,
)
from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Provide a mock vector store for testing.

    Returns:
        MagicMock configured for VectorStore.
    """
    mock = MagicMock(spec=VectorStore)
    mock.add_code_chunks.return_value = 5
    mock.add_code_chunks_batched.return_value = 5
    mock.clear_code_index.return_value = None
    return mock


@pytest.fixture
def secure_project(tmp_path: Path) -> Path:
    """Create a temporary project with test files.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        Path to project root.
    """
    # Create project structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    pass\n")
    (tmp_path / "README.md").write_text("# Test Project\n")

    # Create .gitignore
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n.env\n")

    return tmp_path


class TestIndexerPathTraversalProtection:
    """Test that the indexer blocks path traversal attacks via symlinks."""

    def test_indexer_blocks_symlink_outside_project(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that symlinks pointing outside project root are rejected.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory for external files.
        """
        # Create a file outside the project (using parent of secure_project)
        external_dir = secure_project.parent / "external"
        external_dir.mkdir(exist_ok=True)
        external_file = external_dir / "secret.py"
        external_file.write_text("SECRET_KEY = 'exposed'\n")

        # Create symlink inside project pointing to external file
        symlink_path = secure_project / "src" / "linked.py"
        try:
            symlink_path.symlink_to(external_file)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Discover files - symlink should be excluded
        files = indexer.discover_files()

        # Verify the symlink was not included
        assert symlink_path not in files
        assert all(f.resolve().is_relative_to(secure_project.resolve()) for f in files)

    def test_indexer_blocks_symlink_directory_outside_project(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that symlinked directories pointing outside are rejected.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory for external files.
        """
        # Create an external directory with files (outside project)
        external_dir = secure_project.parent / "external_lib"
        external_dir.mkdir(exist_ok=True)
        (external_dir / "module.py").write_text("def external():\n    pass\n")

        # Create symlink directory inside project
        symlink_dir = secure_project / "linked_lib"
        try:
            symlink_dir.symlink_to(external_dir)
        except OSError:
            pytest.skip("Symlink creation not supported on this platform")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Discover files
        files = indexer.discover_files()

        # Verify files in symlinked directory were not included
        assert not any(f.is_relative_to(symlink_dir) for f in files)
        assert all(f.resolve().is_relative_to(secure_project.resolve()) for f in files)

    def test_validate_path_safety_rejects_external_paths(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that _validate_path_safety rejects paths outside project root.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory for external files.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create external file (outside project)
        external_file = secure_project.parent / "external.py"
        external_file.write_text("print('external')")

        # Test validation
        assert not indexer._validate_path_safety(external_file)

    def test_index_file_rejects_unsafe_paths(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that index_file rejects files with unsafe paths.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory for external files.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create external file (outside project)
        external_file = secure_project.parent / "external.py"
        external_file.write_text("print('external')")

        # Attempt to index external file
        chunks_added = indexer.index_file(external_file)

        # Should return 0 and not call vector store
        assert chunks_added == 0
        mock_vector_store.add_code_chunks.assert_not_called()


class TestIndexerSensitiveFileBlocking:
    """Test that sensitive files are blocked from indexing."""

    @pytest.mark.parametrize(
        "filename",
        [
            ".env",
            ".env.local",
            "production.env",
            "secrets.json",
            "credentials.yaml",
            "id_rsa",
            "id_rsa.pub",
            "private.key",
            "cert.pem",
            "service_account.json",
            "token.json",
            "passwords.txt",
            ".htpasswd",
        ],
    )
    def test_indexer_blocks_sensitive_files(
        self, secure_project: Path, mock_vector_store: MagicMock, filename: str
    ):
        """Test that files matching sensitive patterns are blocked.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            filename: Sensitive filename to test.
        """
        # Create sensitive file
        sensitive_file = secure_project / filename
        sensitive_file.write_text("SENSITIVE_DATA = 'secret'\n")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Check that file is identified as sensitive
        assert indexer._is_sensitive_file(sensitive_file)

        # Verify file is not discovered
        files = indexer.discover_files()
        assert sensitive_file not in files

    def test_indexer_allows_api_client_files(
        self, secure_project: Path, mock_vector_store: MagicMock
    ):
        """Test that API client code files are not blocked.

        The sensitive file patterns should only block DATA files with secrets,
        not code files that handle credentials/APIs.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
        """
        # Create API client files that should NOT be blocked
        allowed_files = [
            "credentials_manager.py",
            "api_client.py",
            "secrets_handler.py",
            "token_service.py",
        ]

        for filename in allowed_files:
            file_path = secure_project / "src" / filename
            file_path.write_text(f"# {filename}\nclass Client:\n    pass\n")

        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # These files should NOT be flagged as sensitive
        for filename in allowed_files:
            file_path = secure_project / "src" / filename
            assert not indexer._is_sensitive_file(file_path)

        # Verify files are discovered
        files = indexer.discover_files()
        discovered_names = {f.name for f in files}

        for filename in allowed_files:
            assert filename in discovered_names

    def test_sensitive_file_patterns_completeness(self):
        """Test that SENSITIVE_FILE_PATTERNS includes expected patterns."""
        # Verify critical patterns are present
        critical_patterns = [
            ".env",
            "*.key",
            "*.pem",
            "id_rsa",
            "credentials.json",
            "secrets.json",
            "passwords.txt",
            "token.json",
        ]

        for pattern in critical_patterns:
            assert pattern in SENSITIVE_FILE_PATTERNS, f"Missing pattern: {pattern}"


class TestIndexerGitignoreRespect:
    """Test that .gitignore patterns are honored by the indexer."""

    def test_indexer_respects_gitignore_patterns(
        self, secure_project: Path, mock_vector_store: MagicMock
    ):
        """Test that files matching .gitignore patterns are excluded.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
        """
        # Create files that should be ignored per .gitignore
        (secure_project / "test.pyc").write_text("compiled")
        pycache_dir = secure_project / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("compiled")
        (secure_project / ".env").write_text("SECRET=value")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Discover files
        files = indexer.discover_files()

        # Verify ignored files are excluded
        file_names = {f.name for f in files}
        assert "test.pyc" not in file_names
        assert "module.pyc" not in file_names
        assert ".env" not in file_names

    def test_indexer_loads_gitignore_on_discovery(
        self, secure_project: Path, mock_vector_store: MagicMock
    ):
        """Test that .gitignore is loaded fresh during file discovery.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
        """
        # Create a file that will be ignored
        (secure_project / "ignored.log").write_text("log data")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Modify .gitignore to add new pattern
        gitignore = secure_project / ".gitignore"
        gitignore.write_text(gitignore.read_text() + "*.log\n")

        # Discover files - should pick up new pattern
        files = indexer.discover_files()

        # Verify .log file is excluded
        assert not any(f.suffix == ".log" for f in files)

    def test_indexer_handles_gitignore_directory_patterns(
        self, secure_project: Path, mock_vector_store: MagicMock
    ):
        """Test that directory patterns in .gitignore work correctly.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
        """
        # Update .gitignore with directory pattern
        gitignore = secure_project / ".gitignore"
        gitignore.write_text("build/\nnode_modules/\n")

        # Create directories with files
        build_dir = secure_project / "build"
        build_dir.mkdir()
        (build_dir / "output.py").write_text("output")

        node_modules = secure_project / "node_modules"
        node_modules.mkdir()
        (node_modules / "lib.js").write_text("lib")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Discover files
        files = indexer.discover_files()

        # Verify files in ignored directories are excluded
        assert not any(f.is_relative_to(build_dir) for f in files)
        assert not any(f.is_relative_to(node_modules) for f in files)

    def test_indexer_without_gitignore(self, tmp_path: Path, mock_vector_store: MagicMock):
        """Test that indexer works when .gitignore doesn't exist.

        Args:
            tmp_path: Temporary directory without .gitignore.
            mock_vector_store: Mock vector store.
        """
        # Create project without .gitignore
        project = tmp_path / "no_gitignore_project"
        project.mkdir()
        (project / "main.py").write_text("def main():\n    pass\n")

        # Initialize indexer
        indexer = CodebaseIndexer(
            project_root=project,
            vector_store=mock_vector_store,
        )

        # Should not raise error
        files = indexer.discover_files()

        # Should discover the file
        assert any(f.name == "main.py" for f in files)


class TestIndexerProjectBoundary:
    """Test that the indexer validates project root boundaries."""

    def test_indexer_rejects_files_outside_project_root(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that files outside project root are rejected.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory for external files.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create file outside project
        external_file = secure_project.parent / "parent_dir" / "external.py"
        external_file.parent.mkdir(exist_ok=True, parents=True)
        external_file.write_text("print('external')")

        # Attempt to index
        chunks = indexer.index_file(external_file)

        # Should return 0 chunks
        assert chunks == 0

    def test_indexer_handles_relative_paths_safely(
        self, secure_project: Path, mock_vector_store: MagicMock
    ):
        """Test that relative paths are resolved safely.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create a file with a complex relative reference
        test_file = secure_project / "src" / "main.py"

        # Get relative path and verify it's within project
        relative = test_file.relative_to(secure_project)
        assert not relative.is_absolute()

        # Validate path safety
        assert indexer._validate_path_safety(test_file)

    def test_indexer_handles_path_with_parent_references(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that paths with ../ are resolved correctly.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create a path that tries to escape via ../
        # When resolved, this should point outside project
        external = secure_project.parent / "external.py"
        external.write_text("external")

        # Path safety validation should catch this
        assert not indexer._validate_path_safety(external)


class TestIndexerSecurityIntegration:
    """Integration tests for combined security features."""

    def test_full_indexing_with_security_filters(
        self, tmp_path: Path, mock_vector_store: MagicMock
    ):
        """Test that a full index build applies all security filters.

        Args:
            tmp_path: Temporary directory for project.
            mock_vector_store: Mock vector store.
        """
        # Create project with various files
        project = tmp_path / "secure_project"
        project.mkdir()

        # Safe files (should be indexed)
        (project / "main.py").write_text("def main():\n    pass\n")
        (project / "utils.py").write_text("def util():\n    pass\n")

        # Sensitive files (should be blocked)
        (project / ".env").write_text("SECRET=value")
        (project / "credentials.json").write_text('{"key": "secret"}')

        # Create .gitignore
        (project / ".gitignore").write_text("*.pyc\n__pycache__/\n")

        # Gitignored files
        (project / "test.pyc").write_text("compiled")

        # External symlink (create external dir outside project)
        external = tmp_path / "external_libs"
        external.mkdir()
        (external / "external.py").write_text("external")

        symlink = project / "linked.py"
        try:
            symlink.symlink_to(external / "external.py")
        except OSError:
            pass  # Skip symlink test if not supported

        # Initialize and build index
        indexer = CodebaseIndexer(
            project_root=project,
            vector_store=mock_vector_store,
        )

        files = indexer.discover_files()

        # Verify only safe files are discovered
        file_names = {f.name for f in files}
        assert "main.py" in file_names
        assert "utils.py" in file_names
        assert ".env" not in file_names
        assert "credentials.json" not in file_names
        assert "test.pyc" not in file_names
        assert "linked.py" not in file_names

    def test_index_single_file_enforces_security(
        self, secure_project: Path, mock_vector_store: MagicMock, tmp_path: Path
    ):
        """Test that index_single_file enforces all security checks.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            tmp_path: Temporary directory.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Try to index sensitive file
        sensitive = secure_project / "credentials.json"
        sensitive.write_text('{"api_key": "secret"}')

        chunks = indexer.index_single_file(sensitive)
        assert chunks == 0

        # Try to index external file
        external = secure_project.parent / "external.py"
        external.write_text("print('external')")

        chunks = indexer.index_single_file(external)
        assert chunks == 0

    def test_security_logging_on_blocks(
        self, secure_project: Path, mock_vector_store: MagicMock, caplog
    ):
        """Test that security blocks are logged appropriately.

        Args:
            secure_project: Project root directory.
            mock_vector_store: Mock vector store.
            caplog: Pytest log capture fixture.
        """
        indexer = CodebaseIndexer(
            project_root=secure_project,
            vector_store=mock_vector_store,
        )

        # Create and attempt to index sensitive file
        sensitive = secure_project / "secrets.json"
        sensitive.write_text('{"password": "secret"}')

        with caplog.at_level("WARNING"):
            indexer.index_file(sensitive)

        # Check for warning log
        assert any("sensitive file" in record.message.lower() for record in caplog.records)
