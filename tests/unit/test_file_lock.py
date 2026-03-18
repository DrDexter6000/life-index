#!/usr/bin/env python3
"""
Unit tests for file_lock.py

Tests cover:
- FileLock class initialization and properties
- Lock acquisition (blocking and non-blocking)
- Lock release and cleanup
- Cross-platform lock behavior (Windows and Unix)
- Timeout handling with poll_interval
- Context manager usage
- Exception classes (LockTimeoutError, LockAcquisitionError)
- Convenience functions (get_journals_lock_path, get_index_lock_path)
- Higher-level helpers (with_journals_lock, with_index_lock)
"""

import os
import platform
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from tools.lib.file_lock import (
    FileLock,
    LockTimeoutError,
    LockAcquisitionError,
    get_journals_lock_path,
    get_index_lock_path,
    with_journals_lock,
    with_index_lock,
)


class TestLockTimeoutError:
    """Tests for LockTimeoutError exception"""

    def test_exception_is_timeout_error(self):
        """LockTimeoutError should be a subclass of TimeoutError"""
        assert issubclass(LockTimeoutError, TimeoutError)

    def test_exception_stores_lock_path(self):
        """Exception should store lock path"""
        lock_path = "/tmp/test.lock"
        timeout = 5.0
        exc = LockTimeoutError(lock_path, timeout)
        assert exc.lock_path == lock_path

    def test_exception_stores_timeout(self):
        """Exception should store timeout value"""
        lock_path = "/tmp/test.lock"
        timeout = 10.5
        exc = LockTimeoutError(lock_path, timeout)
        assert exc.timeout == timeout

    def test_exception_message_format(self):
        """Exception message should be formatted correctly"""
        lock_path = "/tmp/test.lock"
        timeout = 5.0
        exc = LockTimeoutError(lock_path, timeout)
        assert lock_path in str(exc)
        assert "5.0" in str(exc)
        assert "Could not acquire lock" in str(exc)


class TestLockAcquisitionError:
    """Tests for LockAcquisitionError exception"""

    def test_exception_is_os_error(self):
        """LockAcquisitionError should be a subclass of OSError"""
        assert issubclass(LockAcquisitionError, OSError)

    def test_exception_stores_lock_path(self):
        """Exception should store lock path"""
        lock_path = "/tmp/test.lock"
        exc = LockAcquisitionError(lock_path)
        assert exc.lock_path == lock_path

    def test_exception_message_format(self):
        """Exception message should be formatted correctly"""
        lock_path = "/tmp/test.lock"
        exc = LockAcquisitionError(lock_path)
        assert lock_path in str(exc)
        assert "held by another process" in str(exc)


class TestFileLockInit:
    """Tests for FileLock initialization"""

    def test_init_with_string_path(self):
        """FileLock should accept string path"""
        lock = FileLock("/tmp/test.lock")
        assert isinstance(lock.lock_path, Path)
        # Path normalization handles platform differences
        assert "tmp" in str(lock.lock_path)
        assert "test.lock" in str(lock.lock_path)

    def test_init_with_path_object(self):
        """FileLock should accept Path object"""
        path = Path("/tmp/test.lock")
        lock = FileLock(path)
        assert lock.lock_path == path

    def test_init_default_timeout(self):
        """Default timeout should be None"""
        lock = FileLock("/tmp/test.lock")
        assert lock.timeout is None

    def test_init_custom_timeout(self):
        """Custom timeout should be stored"""
        lock = FileLock("/tmp/test.lock", timeout=10.0)
        assert lock.timeout == 10.0

    def test_init_default_poll_interval(self):
        """Default poll_interval should be 0.1"""
        lock = FileLock("/tmp/test.lock")
        assert lock.poll_interval == 0.1

    def test_init_custom_poll_interval(self):
        """Custom poll_interval should be stored"""
        lock = FileLock("/tmp/test.lock", poll_interval=0.5)
        assert lock.poll_interval == 0.5

    def test_init_file_handle_is_none(self):
        """File handle should be None on init"""
        lock = FileLock("/tmp/test.lock")
        assert lock._file_handle is None

    def test_init_locked_is_false(self):
        """Locked state should be False on init"""
        lock = FileLock("/tmp/test.lock")
        assert lock._locked is False


class TestFileLockEnsureLockFile:
    """Tests for _ensure_lock_file method"""

    def test_creates_parent_directory(self, tmp_path):
        """Should create parent directory if it doesn't exist"""
        lock_path = tmp_path / "subdir" / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        assert lock_path.parent.exists()

    def test_creates_lock_file_if_not_exists(self, tmp_path):
        """Should create lock file if it doesn't exist"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        assert lock_path.exists()

    def test_does_not_fail_if_lock_file_exists(self, tmp_path):
        """Should not fail if lock file already exists"""
        lock_path = tmp_path / "test.lock"
        lock_path.touch()
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        assert lock_path.exists()


class TestFileLockAcquireUnix:
    """Tests for Unix-specific lock acquisition"""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix only")
    def test_acquire_unix_blocking_success(self, tmp_path):
        """Should acquire lock on Unix in blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        result = lock._acquire_unix(blocking=True)

        assert result is True
        lock._release_unix()
        os.close(lock._file_handle)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix only")
    def test_acquire_unix_nonblocking_success(self, tmp_path):
        """Should acquire lock on Unix in non-blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        result = lock._acquire_unix(blocking=False)

        assert result is True
        lock._release_unix()
        os.close(lock._file_handle)

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix only")
    def test_acquire_unix_nonblocking_failure(self, tmp_path):
        """Should return False when lock is held by another process"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # First lock acquires
        lock1.acquire(blocking=True)

        # Second lock should fail in non-blocking mode
        lock2._ensure_lock_file()
        lock2._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        result = lock2._acquire_unix(blocking=False)

        assert result is False

        lock1.release()
        os.close(lock2._file_handle)


@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
class TestFileLockAcquireWindows:
    """Tests for Windows-specific lock acquisition"""

    def test_acquire_windows_blocking_with_timeout(self, tmp_path):
        """Windows blocking mode should respect timeout"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path, timeout=0.1, poll_interval=0.01)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        with patch("platform.system", return_value="Windows"):
            with patch("msvcrt.locking") as mock_locking:
                # Simulate lock always failing
                mock_locking.side_effect = OSError("Lock held")

                start_time = time.time()
                result = lock._acquire_windows(blocking=True)
                elapsed = time.time() - start_time

                assert result is False
                assert elapsed < 0.5  # Should respect timeout

    def test_acquire_windows_nonblocking_success(self, tmp_path):
        """Should acquire lock on Windows in non-blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        with patch("msvcrt.locking") as mock_locking:
            result = lock._acquire_windows(blocking=False)
            assert result is True
            mock_locking.assert_called_once()

    def test_acquire_windows_nonblocking_failure(self, tmp_path):
        """Should return False when Windows lock fails"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        with patch("msvcrt.locking") as mock_locking:
            mock_locking.side_effect = OSError("Lock held")
            result = lock._acquire_windows(blocking=False)
            assert result is False


class TestFileLockAcquire:
    """Tests for acquire method"""

    def test_acquire_returns_true_if_already_locked(self, tmp_path):
        """Should return True if already locked"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._locked = True

        result = lock.acquire()

        assert result is True

    def test_acquire_blocking_success(self, tmp_path):
        """Should successfully acquire lock in blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        result = lock.acquire(blocking=True)

        assert result is True
        assert lock._locked is True
        assert lock._file_handle is not None
        lock.release()

    def test_acquire_nonblocking_success(self, tmp_path):
        """Should successfully acquire lock in non-blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        result = lock.acquire(blocking=False)

        assert result is True
        assert lock._locked is True
        lock.release()

    def test_acquire_nonblocking_raises_when_locked(self, tmp_path):
        """Should raise LockAcquisitionError when non-blocking and lock held"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # First lock acquires
        lock1.acquire(blocking=True)

        # Second lock should raise in non-blocking mode
        try:
            with pytest.raises(LockAcquisitionError) as exc_info:
                lock2.acquire(blocking=False)
            assert str(lock_path) in str(exc_info.value)
        finally:
            lock1.release()

    def test_acquire_timeout_raises_when_not_acquired(self, tmp_path):
        """Should raise LockTimeoutError when timeout expires"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path, timeout=0.01, poll_interval=0.001)

        # First lock acquires
        lock1.acquire(blocking=True)

        try:
            with pytest.raises(LockTimeoutError) as exc_info:
                lock2.acquire(blocking=True)
            assert exc_info.value.timeout == 0.01
            assert str(lock_path) in exc_info.value.lock_path
        finally:
            lock1.release()

    def test_acquire_cleans_up_on_unexpected_error(self, tmp_path):
        """Should clean up file handle on unexpected error"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        with patch.object(
            lock, "_ensure_lock_file", side_effect=RuntimeError("Unexpected")
        ):
            with pytest.raises(RuntimeError):
                lock.acquire()

        assert lock._file_handle is None


class TestFileLockRelease:
    """Tests for release method"""

    def test_release_does_nothing_if_not_locked(self, tmp_path):
        """Should do nothing if not locked"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        # Should not raise
        lock.release()

        assert lock._locked is False
        assert lock._file_handle is None

    def test_release_unlocks_and_cleans_up(self, tmp_path):
        """Should release lock and clean up"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        assert lock._locked is True

        lock.release()

        assert lock._locked is False
        assert lock._file_handle is None

    def test_release_handles_close_error(self, tmp_path):
        """Should handle errors when closing file handle"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()

        # Simulate error on close
        with patch("os.close", side_effect=OSError("Close failed")):
            # Should not raise
            lock.release()

        assert lock._locked is False


class TestFileLockTryLock:
    """Tests for try_lock method"""

    def test_try_lock_returns_true_on_success(self, tmp_path):
        """Should return True when lock is acquired"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        result = lock.try_lock()

        assert result is True
        assert lock.is_locked() is True
        lock.release()

    def test_try_lock_returns_false_when_locked(self, tmp_path):
        """Should return False when lock is held by another process"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # First lock acquires
        lock1.acquire()

        try:
            result = lock2.try_lock()
            assert result is False
        finally:
            lock1.release()


class TestFileLockUnlock:
    """Tests for unlock method (alias for release)"""

    def test_unlock_releases_lock(self, tmp_path):
        """unlock should be an alias for release"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        assert lock.is_locked() is True

        lock.unlock()

        assert lock.is_locked() is False


class TestFileLockIsLocked:
    """Tests for is_locked method"""

    def test_is_locked_returns_false_initially(self, tmp_path):
        """Should return False before acquiring lock"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        assert lock.is_locked() is False

    def test_is_locked_returns_true_after_acquire(self, tmp_path):
        """Should return True after acquiring lock"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()

        assert lock.is_locked() is True
        lock.release()

    def test_is_locked_returns_false_after_release(self, tmp_path):
        """Should return False after releasing lock"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        lock.release()

        assert lock.is_locked() is False


class TestFileLockContextManager:
    """Tests for context manager support"""

    def test_enter_acquires_lock(self, tmp_path):
        """__enter__ should acquire lock"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        with lock:
            assert lock.is_locked() is True

    def test_exit_releases_lock(self, tmp_path):
        """__exit__ should release lock"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        with lock:
            pass

        assert lock.is_locked() is False

    def test_exit_releases_lock_on_exception(self, tmp_path):
        """Should release lock even if exception occurs in context"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        try:
            with lock:
                assert lock.is_locked() is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert lock.is_locked() is False

    def test_enter_with_timeout_raises_on_failure(self, tmp_path):
        """Should raise LockTimeoutError when timeout expires in context manager"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path, timeout=0.01, poll_interval=0.001)

        lock1.acquire()

        try:
            with pytest.raises(LockTimeoutError):
                with lock2:
                    pass
        finally:
            lock1.release()

    def test_enter_with_timeout_polls_until_acquired(self, tmp_path):
        """Should poll until lock is acquired or timeout"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path, timeout=5.0, poll_interval=0.01)

        with lock:
            assert lock.is_locked() is True


class TestFileLockDel:
    """Tests for __del__ cleanup"""

    def test_del_releases_lock(self, tmp_path):
        """__del__ should release lock if held"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        assert lock.is_locked() is True

        # Simulate deletion
        lock.__del__()

        assert lock.is_locked() is False

    def test_del_does_nothing_if_not_locked(self, tmp_path):
        """__del__ should do nothing if lock not held"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        # Should not raise
        lock.__del__()


class TestGetJournalsLockPath:
    """Tests for get_journals_lock_path function"""

    def test_returns_path_object(self):
        """Should return a Path object"""
        result = get_journals_lock_path()
        assert isinstance(result, Path)

    def test_returns_correct_filename(self):
        """Should return path with 'journals.lock' filename"""
        result = get_journals_lock_path()
        assert result.name == "journals.lock"

    def test_returns_path_in_cache_dir(self):
        """Should return path in .cache directory"""
        result = get_journals_lock_path()
        assert ".cache" in str(result)

    @patch("tools.lib.config.USER_DATA_DIR", Path("/tmp/test_life_index"))
    def test_returns_path_under_user_data_dir(self):
        """Should return path under USER_DATA_DIR"""
        result = get_journals_lock_path()
        # Use Path comparison to handle Windows/Unix path differences
        assert "tmp" in str(result)
        assert "test_life_index" in str(result)


class TestGetIndexLockPath:
    """Tests for get_index_lock_path function"""

    def test_returns_path_object(self):
        """Should return a Path object"""
        result = get_index_lock_path()
        assert isinstance(result, Path)

    def test_returns_correct_filename(self):
        """Should return path with 'index.lock' filename"""
        result = get_index_lock_path()
        assert result.name == "index.lock"

    def test_returns_path_in_cache_dir(self):
        """Should return path in .cache directory"""
        result = get_index_lock_path()
        assert ".cache" in str(result)

    @patch("tools.lib.config.USER_DATA_DIR", Path("/tmp/test_life_index"))
    def test_returns_path_under_user_data_dir(self):
        """Should return path under USER_DATA_DIR"""
        result = get_index_lock_path()
        # Use Path comparison to handle Windows/Unix path differences
        assert "tmp" in str(result)
        assert "test_life_index" in str(result)


class TestWithJournalsLock:
    """Tests for with_journals_lock convenience function"""

    def test_executes_function_with_lock(self):
        """Should execute function with journals lock held"""
        mock_func = MagicMock(return_value="result")

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            result = with_journals_lock(mock_func, "arg1", key="value")

            mock_func.assert_called_once_with("arg1", key="value")
            assert result == "result"

    def test_uses_default_timeout(self):
        """Should use default timeout of 30.0 seconds"""
        mock_func = MagicMock()

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            with_journals_lock(mock_func)

            mock_lock_class.assert_called_once()
            call_kwargs = mock_lock_class.call_args[1]
            assert call_kwargs.get("timeout") == 30.0

    def test_allows_custom_timeout(self):
        """Should allow custom timeout"""
        mock_func = MagicMock()

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            with_journals_lock(mock_func, timeout=60.0)

            call_kwargs = mock_lock_class.call_args[1]
            assert call_kwargs.get("timeout") == 60.0

    def test_propagates_exception(self):
        """Should propagate exceptions from function"""
        mock_func = MagicMock(side_effect=ValueError("Test error"))

        with patch("tools.lib.file_lock.FileLock"):
            with pytest.raises(ValueError, match="Test error"):
                with_journals_lock(mock_func)


class TestWithIndexLock:
    """Tests for with_index_lock convenience function"""

    def test_executes_function_with_lock(self):
        """Should execute function with index lock held"""
        mock_func = MagicMock(return_value="result")

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            result = with_index_lock(mock_func, "arg1", key="value")

            mock_func.assert_called_once_with("arg1", key="value")
            assert result == "result"

    def test_uses_default_timeout(self):
        """Should use default timeout of 60.0 seconds"""
        mock_func = MagicMock()

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            with_index_lock(mock_func)

            mock_lock_class.assert_called_once()
            call_kwargs = mock_lock_class.call_args[1]
            assert call_kwargs.get("timeout") == 60.0

    def test_allows_custom_timeout(self):
        """Should allow custom timeout"""
        mock_func = MagicMock()

        with patch("tools.lib.file_lock.FileLock") as mock_lock_class:
            mock_lock = MagicMock()
            mock_lock_class.return_value = mock_lock

            with_index_lock(mock_func, timeout=120.0)

            call_kwargs = mock_lock_class.call_args[1]
            assert call_kwargs.get("timeout") == 120.0

    def test_propagates_exception(self):
        """Should propagate exceptions from function"""
        mock_func = MagicMock(side_effect=ValueError("Test error"))

        with patch("tools.lib.file_lock.FileLock"):
            with pytest.raises(ValueError, match="Test error"):
                with_index_lock(mock_func)


class TestFileLockCrossPlatform:
    """Cross-platform integration tests"""

    def test_cross_process_lock_competition(self, tmp_path):
        """Should handle concurrent lock attempts"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # First acquires
        assert lock1.acquire(blocking=False) is True

        # Second fails in non-blocking mode
        assert lock2.try_lock() is False

        # First releases
        lock1.release()

        # Second can now acquire
        assert lock2.acquire(blocking=False) is True
        lock2.release()

    def test_multiple_acquire_calls_idempotent(self, tmp_path):
        """Multiple acquire calls should be idempotent"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        first_handle = lock._file_handle

        # Second acquire should return True without error
        result = lock.acquire()

        assert result is True
        assert lock._file_handle == first_handle
        lock.release()

    def test_release_idempotent(self, tmp_path):
        """Multiple release calls should not raise"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        lock.release()

        # Second release should not raise
        lock.release()

        assert lock.is_locked() is False


class TestFileLockEdgeCases:
    """Edge case tests"""

    def test_lock_file_with_special_characters(self, tmp_path):
        """Should handle lock paths with special characters"""
        lock_path = tmp_path / "test-file_123.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        assert lock.is_locked() is True
        lock.release()

    def test_lock_in_deeply_nested_directory(self, tmp_path):
        """Should create deeply nested directories"""
        lock_path = tmp_path / "a" / "b" / "c" / "d" / "test.lock"
        lock = FileLock(lock_path)

        lock.acquire()
        assert lock_path.exists()
        lock.release()

    def test_concurrent_lock_timeout_with_short_interval(self, tmp_path):
        """Should respect timeout with very short poll interval"""
        lock_path = tmp_path / "test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path, timeout=0.05, poll_interval=0.005)

        lock1.acquire()

        try:
            start = time.time()
            with pytest.raises(LockTimeoutError):
                lock2.acquire()
            elapsed = time.time() - start

            # Should complete near timeout (with some tolerance)
            assert elapsed < 0.2
        finally:
            lock1.release()


class TestFileLockWindowsBlocking:
    """Tests for Windows blocking mode with various scenarios"""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_acquire_windows_blocking_with_timeout_times_out(self, tmp_path):
        """Windows blocking with timeout should return False on timeout"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path, timeout=0.01, poll_interval=0.001)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        # Always fail to simulate timeout
        with patch("platform.system", return_value="Windows"):
            with patch("msvcrt.locking", side_effect=OSError("Lock held")):
                start_time = time.time()
                result = lock._acquire_windows(blocking=True)
                elapsed = time.time() - start_time

        assert result is False
        assert elapsed < 0.1  # Should respect timeout
        os.close(lock._file_handle)


class TestFileLockExceptionCleanup:
    """Tests for exception handling and cleanup"""

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_acquire_re_raises_lock_acquisition_error(self, tmp_path):
        """Should raise LockAcquisitionError in non-blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        try:
            with patch("platform.system", return_value="Windows"):
                with patch("msvcrt.locking", side_effect=OSError("Locked")):
                    with pytest.raises(LockAcquisitionError):
                        lock.acquire(blocking=False)
        finally:
            # Clean up the file handle if it wasn't closed
            try:
                os.close(lock._file_handle)
            except (OSError, TypeError):
                pass

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_acquire_cleans_up_on_exception_in_windows_acquire(self, tmp_path):
        """Should clean up file handle on unexpected exception during Windows acquire"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        try:
            with patch("platform.system", return_value="Windows"):
                with patch("msvcrt.locking", side_effect=RuntimeError("Unexpected")):
                    with pytest.raises(RuntimeError, match="Unexpected"):
                        lock.acquire()
        finally:
            # Verify file handle was cleaned up
            assert lock._file_handle is None
            assert lock._locked is False

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
    def test_acquire_cleans_up_file_handle_on_unexpected_error(self, tmp_path):
        """Should clean up file handle on unexpected error during acquire"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        # Simulate an unexpected error during lock acquisition (not OSError)
        try:
            with patch("platform.system", return_value="Windows"):
                with patch("msvcrt.locking", side_effect=RuntimeError("Unexpected")):
                    with pytest.raises(RuntimeError, match="Unexpected"):
                        lock.acquire()
        finally:
            # Clean up
            if lock._file_handle is not None:
                try:
                    os.close(lock._file_handle)
                except OSError:
                    pass
            assert lock._file_handle is None
            assert lock._locked is False


class TestFileLockAcquireUnixErrorHandling:
    """Tests for Unix acquire error handling (via mocking)"""

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix only")
    def test_acquire_unix_reraises_unexpected_error(self, tmp_path):
        """Should re-raise unexpected errors in blocking mode"""
        lock_path = tmp_path / "test.lock"
        lock = FileLock(lock_path)
        lock._ensure_lock_file()
        lock._file_handle = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)

        try:
            with patch("fcntl.flock", side_effect=IOError("Unexpected")):
                with pytest.raises(IOError, match="Unexpected"):
                    lock._acquire_unix(blocking=True)
        finally:
            os.close(lock._file_handle)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
