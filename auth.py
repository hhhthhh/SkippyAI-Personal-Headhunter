import os
import hmac
import time
import hashlib
import secrets
import threading
from datetime import datetime, timezone
import streamlit as st
from dotenv import set_key

import database as db

ENV_FILE = ".env"
PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256
MAX_USERNAME_LENGTH = 64

_auth_lock = threading.Lock()
_active_sessions: dict[str, dict] = {}

# Pre-computed dummy hash so failed lookups always perform full constant-time PBKDF2 work
_DUMMY_SALT_HEX = "00" * SALT_BYTES
_DUMMY_HASH_HEX = hashlib.pbkdf2_hmac(
    PBKDF2_ALGORITHM,
    b"skippy-dummy-constant-time-password",
    bytes.fromhex(_DUMMY_SALT_HEX),
    PBKDF2_ITERATIONS,
).hex()
_DUMMY_STORED_HASH = f"pbkdf2_sha256:{PBKDF2_ITERATIONS}:{_DUMMY_SALT_HEX}:{_DUMMY_HASH_HEX}"


from database import secure_file_permissions as _secure_file_permissions, set_env_var_safe

_auth_tables_initialized = False

def _set_env_var_safe(key: str, value: str):
    set_env_var_safe(key, value, env_file=ENV_FILE)


def init_auth_tables():
    """Creates authentication and brute-force protection tables in SQLite if not present."""
    global _auth_tables_initialized
    if _auth_tables_initialized:
        return
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_credentials (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_security_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    first_failed_at REAL NOT NULL DEFAULT 0,
                    locked_until REAL NOT NULL DEFAULT 0,
                    lockout_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO auth_security_state (
                    id, failed_attempts, first_failed_at, locked_until, lockout_count
                ) VALUES (1, 0, 0, 0, 0)
                """
            )
        _auth_tables_initialized = True
    finally:
        conn.close()
    db._secure_db_file_permissions()


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a 128-bit cryptographic salt.
    Returns format: `pbkdf2_sha256:<iterations>:<salt_hex>:<hash_hex>`
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        int(iterations),
    )
    return f"pbkdf2_sha256:{int(iterations)}:{salt.hex()}:{derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifies a password against a PBKDF2-HMAC-SHA256 hash string using constant-time comparison.
    Supports both `:` and `$` delimiters (`pbkdf2_sha256:600000:salt:hash`).
    """
    if not isinstance(password, str) or not isinstance(stored_hash, str) or not stored_hash:
        stored_hash = _DUMMY_STORED_HASH
        valid_format = False
    else:
        valid_format = True

    sep = ":" if ":" in stored_hash else "$"
    parts = stored_hash.strip().split(sep)
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        parts = _DUMMY_STORED_HASH.split(":")
        valid_format = False

    try:
        iterations = int(parts[1])
        salt_bytes = bytes.fromhex(parts[2])
        expected_hex = parts[3].lower()
        if iterations < 10_000 or iterations > 10_000_000 or not salt_bytes or not expected_hex:
            raise ValueError("Invalid parameters")
    except ValueError:
        iterations = PBKDF2_ITERATIONS
        salt_bytes = bytes.fromhex(_DUMMY_SALT_HEX)
        expected_hex = _DUMMY_HASH_HEX
        valid_format = False

    computed_hex = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        (password or "").encode("utf-8"),
        salt_bytes,
        iterations,
    ).hex()

    matches = hmac.compare_digest(computed_hex, expected_hex)
    return bool(matches and valid_format)


def _constant_time_username_match(input_username: str, expected_username: str) -> bool:
    """Compares two usernames in constant time using SHA-256 digests."""
    a = hashlib.sha256((input_username or "").strip().encode("utf-8")).digest()
    b = hashlib.sha256((expected_username or "").strip().encode("utf-8")).digest()
    return hmac.compare_digest(a, b)


def _load_db_credentials() -> dict | None:
    init_auth_tables()
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT username, password_hash, updated_at FROM auth_credentials WHERE id = 1")
        row = cur.fetchone()
        if row and row[0] and row[1]:
            return {
                "username": str(row[0]).strip(),
                "password_hash": str(row[1]).strip(),
                "updated_at": str(row[2]),
                "source": "database",
            }
    except Exception:
        pass
    finally:
        conn.close()
    return None


def _save_db_credentials(username: str, password_hash: str):
    init_auth_tables()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    conn = db.get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO auth_credentials (id, username, password_hash, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    username = excluded.username,
                    password_hash = excluded.password_hash,
                    updated_at = excluded.updated_at
                """,
                (username.strip(), password_hash.strip(), now_str),
            )
    finally:
        conn.close()
    db._secure_db_file_permissions()


def get_configured_credentials() -> dict | None:
    """
    Resolves active login credentials in priority order:
    1. Environment variable `SKIPPY_AUTH_PASSWORD` (plaintext override from hosting platform)
    2. Database `auth_credentials` table in `skippy.db`
    3. Environment variable `SKIPPY_AUTH_PASSWORD_HASH` (synced into DB if DB is empty)
    """
    env_username = os.environ.get("SKIPPY_AUTH_USERNAME", "").strip()
    env_plain_password = os.environ.get("SKIPPY_AUTH_PASSWORD", "")
    env_password_hash = os.environ.get("SKIPPY_AUTH_PASSWORD_HASH", "").strip()

    # 1. Explicit plaintext env var override (common in cloud dashboards like Render/Railway/Fly)
    if env_plain_password:
        return {
            "username": env_username or "admin",
            "plain_password": env_plain_password,
            "source": "env_plain",
        }

    # 2. Check SQLite database
    db_creds = _load_db_credentials()
    if db_creds:
        # If SKIPPY_AUTH_PASSWORD_HASH is also set in env, prefer env hash so env overrides work
        if env_password_hash:
            return {
                "username": env_username or db_creds["username"] or "admin",
                "password_hash": env_password_hash,
                "source": "env_hash",
            }
        return db_creds

    # 3. Hash configured in .env / environment variables
    if env_password_hash:
        resolved_user = env_username or "admin"
        try:
            _save_db_credentials(resolved_user, env_password_hash)
        except Exception:
            pass
        return {
            "username": resolved_user,
            "password_hash": env_password_hash,
            "source": "env_hash",
        }

    return None


def is_auth_configured() -> bool:
    """Returns True if login credentials have been configured via UI, SQLite, or environment."""
    return get_configured_credentials() is not None


def save_auth_credentials(username: str, password: str) -> None:
    """
    Hashes `password` with PBKDF2-HMAC-SHA256 and persists both username and hash
    to `skippy.db` and `.env` (0600 permissions). Never stores plaintext passwords.
    """
    clean_user = (username or "").strip()
    if not clean_user:
        raise ValueError("Username cannot be empty.")
    if len(clean_user) > MAX_USERNAME_LENGTH:
        raise ValueError(f"Username cannot exceed {MAX_USERNAME_LENGTH} characters.")
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters.")

    pw_hash = hash_password(password)
    _save_db_credentials(clean_user, pw_hash)
    _set_env_var_safe("SKIPPY_AUTH_USERNAME", clean_user)
    _set_env_var_safe("SKIPPY_AUTH_PASSWORD_HASH", pw_hash)
    # If a plaintext password was lingering in os.environ, clear it so the new hash is authoritative
    if "SKIPPY_AUTH_PASSWORD" in os.environ:
        os.environ.pop("SKIPPY_AUTH_PASSWORD", None)


def verify_credentials(username: str, password: str) -> bool:
    """
    Verifies username and password in constant time.
    Always runs PBKDF2/HMAC verification even when username does not match to prevent username enumeration.
    """
    creds = get_configured_credentials()
    if not creds:
        verify_password(password or "", _DUMMY_STORED_HASH)
        return False

    user_ok = _constant_time_username_match(username, creds.get("username", "admin"))

    if creds.get("source") == "env_plain":
        # Perform dummy PBKDF2 so timing is indistinguishable, then constant-time compare digests
        verify_password(password or "", _DUMMY_STORED_HASH)
        pw_a = hashlib.sha256((password or "").encode("utf-8")).digest()
        pw_b = hashlib.sha256(creds.get("plain_password", "").encode("utf-8")).digest()
        pw_ok = hmac.compare_digest(pw_a, pw_b)
    else:
        pw_ok = verify_password(password or "", creds.get("password_hash", ""))

    return bool(user_ok and pw_ok)


def _get_max_login_attempts() -> int:
    try:
        return max(3, int(os.environ.get("SKIPPY_MAX_LOGIN_ATTEMPTS", "5")))
    except ValueError:
        return 5


def _get_base_lockout_seconds() -> int:
    try:
        minutes = max(1, int(os.environ.get("SKIPPY_LOCKOUT_MINUTES", "15")))
        return minutes * 60
    except ValueError:
        return 15 * 60


def _get_session_timeout_seconds() -> int:
    try:
        minutes = max(5, int(os.environ.get("SKIPPY_SESSION_TIMEOUT_MINUTES", "720")))
        return minutes * 60
    except ValueError:
        return 720 * 60


def check_lockout_status() -> tuple[bool, int, int]:
    """
    Checks whether login is currently locked out due to brute-force attempts.
    Returns `(is_locked, seconds_remaining, failed_attempts)`.
    """
    init_auth_tables()
    now = time.time()
    max_attempts = _get_max_login_attempts()

    with _auth_lock:
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT failed_attempts, first_failed_at, locked_until, lockout_count "
                "FROM auth_security_state WHERE id = 1"
            )
            row = cur.fetchone()
            if not row:
                return False, 0, 0

            failed_attempts, first_failed_at, locked_until, lockout_count = (
                int(row[0] or 0),
                float(row[1] or 0.0),
                float(row[2] or 0.0),
                int(row[3] or 0),
            )

            if locked_until > now:
                remaining = max(1, int(round(locked_until - now)))
                return True, remaining, failed_attempts

            # If a previous lockout just expired, reset failed_attempts counter so user gets fresh tries
            if locked_until > 0 and locked_until <= now:
                with conn:
                    conn.execute(
                        "UPDATE auth_security_state SET failed_attempts = 0, locked_until = 0 WHERE id = 1"
                    )
                return False, 0, 0

            # Reset rolling attempt window if last failure window was more than 15 minutes ago
            if failed_attempts > 0 and first_failed_at > 0 and (now - first_failed_at) > 900:
                with conn:
                    conn.execute(
                        "UPDATE auth_security_state SET failed_attempts = 0, first_failed_at = 0, lockout_count = 0 WHERE id = 1"
                    )
                return False, 0, 0

            return False, 0, min(failed_attempts, max_attempts)
        finally:
            conn.close()


def record_failed_attempt() -> tuple[bool, int, int]:
    """
    Records a failed login attempt and triggers a lockout if `SKIPPY_MAX_LOGIN_ATTEMPTS` is reached.
    Returns `(is_now_locked, lockout_seconds_remaining, attempts_remaining)`.
    """
    init_auth_tables()
    now = time.time()
    max_attempts = _get_max_login_attempts()
    base_lockout = _get_base_lockout_seconds()

    with _auth_lock:
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT failed_attempts, first_failed_at, locked_until, lockout_count "
                "FROM auth_security_state WHERE id = 1"
            )
            row = cur.fetchone()
            failed_attempts = int(row[0] or 0) if row else 0
            first_failed_at = float(row[1] or 0.0) if row else 0.0
            locked_until = float(row[2] or 0.0) if row else 0.0
            lockout_count = int(row[3] or 0) if row else 0

            if locked_until > now:
                return True, max(1, int(round(locked_until - now))), 0

            if locked_until > 0 and locked_until <= now:
                failed_attempts = 0
                locked_until = 0.0

            if failed_attempts == 0 or (now - first_failed_at) > 900:
                failed_attempts = 1
                first_failed_at = now
            else:
                failed_attempts += 1

            if failed_attempts >= max_attempts:
                lockout_count += 1
                # Exponential backoff on repeated lockouts, capped at 1 hour
                multiplier = min(2 ** (lockout_count - 1), 4)
                duration = min(base_lockout * multiplier, 3600)
                locked_until = now + duration
                with conn:
                    conn.execute(
                        """
                        UPDATE auth_security_state
                        SET failed_attempts = ?, first_failed_at = ?, locked_until = ?, lockout_count = ?
                        WHERE id = 1
                        """,
                        (failed_attempts, first_failed_at, locked_until, lockout_count),
                    )
                return True, int(duration), 0
            else:
                with conn:
                    conn.execute(
                        """
                        UPDATE auth_security_state
                        SET failed_attempts = ?, first_failed_at = ?, locked_until = 0
                        WHERE id = 1
                        """,
                        (failed_attempts, first_failed_at),
                    )
                attempts_left = max(0, max_attempts - failed_attempts)
                return False, 0, attempts_left
        finally:
            conn.close()


def reset_failed_attempts() -> None:
    """Clears all failed login counters and lockouts upon successful authentication."""
    init_auth_tables()
    with _auth_lock:
        conn = db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE auth_security_state
                    SET failed_attempts = 0, first_failed_at = 0, locked_until = 0, lockout_count = 0
                    WHERE id = 1
                    """
                )
        finally:
            conn.close()


def login_user(username: str) -> str:
    """Creates a new server-verified authenticated session for `username`."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    clean_user = username.strip()
    with _auth_lock:
        _active_sessions[token] = {
            "username": clean_user,
            "created_at": now,
            "last_seen": now,
        }
    st.session_state["authenticated"] = True
    st.session_state["auth_token"] = token
    st.session_state["auth_username"] = clean_user
    try:
        st.query_params["session"] = token
    except Exception:
        pass
    reset_failed_attempts()
    return token


def logout_user(revoke_all: bool = False) -> None:
    """Terminates the current authenticated session (or all sessions if `revoke_all=True`)."""
    token = st.session_state.get("auth_token") or st.query_params.get("session")
    with _auth_lock:
        if revoke_all:
            _active_sessions.clear()
        elif token and token in _active_sessions:
            del _active_sessions[token]

    for key in ("authenticated", "auth_token", "auth_username"):
        st.session_state.pop(key, None)
    try:
        st.query_params.pop("session", None)
    except Exception:
        pass


def is_authenticated() -> bool:
    """
    Validates that the current browser session holds an active, non-expired server session token.
    Automatically expires idle sessions after `SKIPPY_SESSION_TIMEOUT_MINUTES`.
    """
    token = st.session_state.get("auth_token") or st.query_params.get("session")
    if not token or not isinstance(token, str):
        if st.session_state.get("authenticated"):
            logout_user()
        return False

    now = time.time()
    timeout_secs = _get_session_timeout_seconds()

    with _auth_lock:
        session_info = _active_sessions.get(token)
        if not session_info:
            # Session was revoked or server restarted
            st.session_state.pop("authenticated", None)
            st.session_state.pop("auth_token", None)
            st.session_state.pop("auth_username", None)
            try:
                st.query_params.pop("session", None)
            except Exception:
                pass
            return False

        if (now - session_info.get("last_seen", 0)) > timeout_secs:
            del _active_sessions[token]
            st.session_state.pop("authenticated", None)
            st.session_state.pop("auth_token", None)
            st.session_state.pop("auth_username", None)
            try:
                st.query_params.pop("session", None)
            except Exception:
                pass
            st.session_state["auth_expired_notice"] = True
            return False

        session_info["last_seen"] = now
        st.session_state["authenticated"] = True
        st.session_state["auth_token"] = token
        st.session_state["auth_username"] = session_info.get("username", "admin")
        try:
            if st.query_params.get("session") != token:
                st.query_params["session"] = token
        except Exception:
            pass
        return True


def _format_duration(seconds: int) -> str:
    mins, secs = divmod(max(0, int(seconds)), 60)
    if mins > 0:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"


def render_login_page() -> None:
    """Renders the full-screen secure login or first-time admin setup page."""
    from utils import inject_interactive_hover_halo_effects
    inject_interactive_hover_halo_effects()

    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] { display: none !important; }
            [data-testid="stSidebarNav"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }
            .skippy-auth-header {
                text-align: center;
                margin-bottom: 0.25rem;
            }
            .skippy-auth-subtitle {
                text-align: center;
                opacity: 0.78;
                font-size: 0.95rem;
                margin-bottom: 1.25rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1, 1.35, 1])

    with center_col:
        st.markdown("<div style='height: 6vh;'></div>", unsafe_allow_html=True)

        if st.session_state.pop("auth_expired_notice", False):
            st.info("🔒 Your session expired due to inactivity. Please sign in again.")

        configured = is_auth_configured()

        with st.container(border=True):
            if configured:
                st.markdown("<h2 class='skippy-auth-header'>🦘 Skippy CRM</h2>", unsafe_allow_html=True)
                st.markdown(
                    "<p class='skippy-auth-subtitle'>🔒 Private Instance — Authorized Access Only</p>",
                    unsafe_allow_html=True,
                )

                is_locked, remaining_secs, _ = check_lockout_status()

                if is_locked:
                    st.error(
                        f"🛑 **Account Temporarily Locked**\n\n"
                        f"Too many failed sign-in attempts. Please wait **{_format_duration(remaining_secs)}** before trying again."
                    )
                    if st.button("🔄 Refresh Lockout Timer", width="stretch"):
                        st.rerun()
                else:
                    with st.form("skippy_login_form", clear_on_submit=False):
                        username_input = st.text_input(
                            "Username",
                            placeholder="Enter your username",
                            autocomplete="username",
                        )
                        password_input = st.text_input(
                            "Password",
                            type="password",
                            placeholder="Enter your password",
                            autocomplete="current-password",
                        )
                        submitted = st.form_submit_button(
                            "🔓 Sign In",
                            type="primary",
                            width="stretch",
                        )

                    if submitted:
                        # Re-check lockout right before verifying
                        locked_now, rem_now, _ = check_lockout_status()
                        if locked_now:
                            st.error(
                                f"🛑 Account is locked. Try again in **{_format_duration(rem_now)}**."
                            )
                        elif not username_input.strip() or not password_input:
                            st.warning("Please enter both your username and password.")
                        elif verify_credentials(username_input, password_input):
                            creds = get_configured_credentials() or {}
                            canonical_user = creds.get("username", username_input.strip())
                            login_user(canonical_user)
                            st.rerun()
                        else:
                            now_locked, lock_secs, attempts_left = record_failed_attempt()
                            if now_locked:
                                st.error(
                                    f"🛑 Too many failed attempts. Login is locked for **{_format_duration(lock_secs)}**."
                                )
                            else:
                                st.error(
                                    f"❌ Invalid username or password. "
                                    f"({attempts_left} attempt{'s' if attempts_left != 1 else ''} remaining before lockout)"
                                )
            else:
                st.markdown("<h2 class='skippy-auth-header'>🛡️ Secure Your Skippy Instance</h2>", unsafe_allow_html=True)
                st.markdown(
                    "<p class='skippy-auth-subtitle'>Create your administrator login to lock down this deployment.</p>",
                    unsafe_allow_html=True,
                )
                st.info(
                    "Your password is salted and hashed locally with **PBKDF2-HMAC-SHA256 (600,000 iterations)** "
                    "and is never stored in plaintext.",
                    icon="🔐",
                )

                with st.form("skippy_initial_setup_form", clear_on_submit=False):
                    new_username = st.text_input(
                        "Admin Username",
                        value="admin",
                        help="Username you will use to sign in to Skippy.",
                        autocomplete="username",
                    )
                    new_password = st.text_input(
                        f"Admin Password (min. {MIN_PASSWORD_LENGTH} characters)",
                        type="password",
                        placeholder="Create a strong password",
                        autocomplete="new-password",
                    )
                    confirm_password = st.text_input(
                        "Confirm Password",
                        type="password",
                        placeholder="Re-enter your password",
                        autocomplete="new-password",
                    )
                    setup_submitted = st.form_submit_button(
                        "🔐 Save Credentials & Sign In",
                        type="primary",
                        width="stretch",
                    )

                if setup_submitted:
                    clean_user = new_username.strip()
                    if not clean_user:
                        st.warning("Please enter an admin username.")
                    elif len(clean_user) > MAX_USERNAME_LENGTH:
                        st.warning(f"Username must be {MAX_USERNAME_LENGTH} characters or fewer.")
                    elif len(new_password) < MIN_PASSWORD_LENGTH:
                        st.warning(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match. Please re-enter carefully.")
                    else:
                        save_auth_credentials(clean_user, new_password)
                        login_user(clean_user)
                        st.toast("Admin credentials created and secured!", icon="🔐")
                        st.rerun()


def render_sidebar_auth_controls() -> None:
    """Renders the logged-in user status, Logout button, and Change Password form in the sidebar."""
    if not is_authenticated():
        return

    username = st.session_state.get("auth_username", "admin")
    creds = get_configured_credentials() or {}
    is_env_plain = creds.get("source") == "env_plain"

    st.sidebar.markdown("---")
    col_user, col_logout = st.sidebar.columns([1.5, 1])
    with col_user:
        st.markdown(f"🔐 **`{username}`**")
    with col_logout:
        if st.button("Log Out", key="btn_sidebar_logout", width="stretch"):
            logout_user()
            st.rerun()

    with st.sidebar.expander("🛡️ Account & Password"):
        if is_env_plain:
            st.caption(
                "Credentials are currently enforced via the `SKIPPY_AUTH_PASSWORD` environment variable. "
                "Update your hosting environment variables to change them."
            )
        else:
            with st.form("sidebar_change_password_form", clear_on_submit=True):
                updated_username = st.text_input("Username", value=username)
                current_pw = st.text_input("Current Password", type="password")
                new_pw = st.text_input(
                    f"New Password (min. {MIN_PASSWORD_LENGTH} chars)",
                    type="password",
                )
                confirm_pw = st.text_input("Confirm New Password", type="password")
                save_pw_btn = st.form_submit_button("Update Credentials", width="stretch")

            if save_pw_btn:
                if not current_pw or not new_pw:
                    st.warning("Please fill in your current and new password.")
                elif not verify_credentials(username, current_pw):
                    st.error("❌ Current password is incorrect.")
                elif len(new_pw) < MIN_PASSWORD_LENGTH:
                    st.warning(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")
                elif new_pw != confirm_pw:
                    st.error("New passwords do not match.")
                elif not updated_username.strip():
                    st.warning("Username cannot be empty.")
                else:
                    save_auth_credentials(updated_username.strip(), new_pw)
                    # Revoke all existing sessions and issue a fresh token for the current session
                    logout_user(revoke_all=True)
                    login_user(updated_username.strip())
                    st.success("✅ Credentials updated!")


def enforce_authentication() -> None:
    """
    Gatekeeper function that blocks unauthenticated execution.
    If not authenticated, renders the login screen and halts script execution via `st.stop()`.
    """
    if not is_authenticated():
        render_login_page()
        st.stop()
