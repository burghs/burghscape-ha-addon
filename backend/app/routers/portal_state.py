"""Shared state for portal authentication."""
# In production, use Redis or JWT tokens

# Session token -> user_id mapping
portal_sessions: dict = {}


popup_evaluated_sessions: set[str] = set()
