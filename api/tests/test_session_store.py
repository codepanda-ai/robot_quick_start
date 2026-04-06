"""Tests for ISessionStore contract per SPEC.md §Session Store Schema.

Verifies:
- get() returns default session (phase=idle, empty profile) for new users
- save() persists and get() retrieves the full SessionState
- get() returns a deep copy — mutations don't affect stored state
- clear() resets a user's session back to default
- Thread-safe: concurrent access does not corrupt state
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import threading
from core.session_store import InMemorySessionStore
from interfaces.models import SessionState, Phase, IntentProfile, Budget


class TestSessionStoreContract:
    """ISessionStore interface contract — any implementation must pass these."""

    def _make_store(self):
        return InMemorySessionStore()

    def test_new_user_gets_default_session(self):
        """SPEC: get() returns default if none exists — phase=idle, empty intent_profile."""
        store = self._make_store()
        session = store.get("unknown_user")
        assert session.phase == Phase.IDLE
        assert session.intent_profile.activity is None
        assert session.intent_profile.budget is None
        assert session.suggestions == []
        assert session.selected_suggestion is None
        assert session.buddy_candidates == []
        assert session.selected_buddies == []
        assert session.confirmation_status is None

    def test_save_persists_full_state(self):
        """SPEC: save() persists the full SessionState for a user."""
        store = self._make_store()
        state = SessionState(
            phase=Phase.GATHERING,
            intent_profile=IntentProfile(activity="hiking", budget=Budget.LOW),
        )
        store.save("user_1", state)
        retrieved = store.get("user_1")
        assert retrieved.phase == Phase.GATHERING
        assert retrieved.intent_profile.activity == "hiking"
        assert retrieved.intent_profile.budget == Budget.LOW

    def test_get_returns_deep_copy(self):
        """SPEC: Mutations to retrieved state must not affect stored state."""
        store = self._make_store()
        store.save("user_1", SessionState(phase=Phase.GATHERING))
        copy = store.get("user_1")
        copy.phase = Phase.CONFIRMED  # Mutate the copy
        original = store.get("user_1")
        assert original.phase == Phase.GATHERING  # Store unaffected

    def test_clear_resets_to_default(self):
        """SPEC: clear() resets session for user."""
        store = self._make_store()
        store.save("user_1", SessionState(phase=Phase.CONFIRMED))
        store.clear("user_1")
        session = store.get("user_1")
        assert session.phase == Phase.IDLE

    def test_clear_nonexistent_user_is_noop(self):
        """SPEC: clear() on unknown user should not raise."""
        store = self._make_store()
        store.clear("nobody")  # Should not raise

    def test_independent_users(self):
        """Different users have independent sessions."""
        store = self._make_store()
        store.save("user_a", SessionState(phase=Phase.GATHERING))
        store.save("user_b", SessionState(phase=Phase.CONFIRMED))
        assert store.get("user_a").phase == Phase.GATHERING
        assert store.get("user_b").phase == Phase.CONFIRMED

    def test_thread_safety(self):
        """SPEC: Thread-safe for concurrent access."""
        store = self._make_store()
        errors = []

        def writer(uid):
            try:
                for i in range(50):
                    store.save(uid, SessionState(phase=Phase.GATHERING))
                    store.get(uid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(f"user_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
