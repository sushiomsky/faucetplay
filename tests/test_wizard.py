"""
OnboardingWizard GUI integration tests.

Two suites:
  TestWizardUI          — no credentials needed; verifies the UI renders
                          and basic validation works.
  TestWizardSetup       — uses real DuckDice credentials to walk all 5
                          wizard steps end-to-end and verifies the config
                          is populated correctly.

Requires: tk_root fixture (needs a display — provided by xvfb-run in CI).
          DUCKDICE_COOKIE for TestWizardSetup tests.
"""
import pytest
from tests.conftest import pump, wait_for


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wizard(tk_root, api_key="", cookie="", on_complete=None):
    from core.config import BotConfig
    from gui.wizard import OnboardingWizard

    cfg = BotConfig()
    completed = []
    cb = on_complete or (lambda: completed.append(True))

    wizard = OnboardingWizard(tk_root, config=cfg, on_complete=cb)
    wizard._api_key_var.set(api_key)
    wizard._cookie_var.set(cookie)
    pump(tk_root, 0.2)
    return wizard, cfg, completed


# ---------------------------------------------------------------------------
# Suite 1 — UI smoke tests (no credentials required)
# ---------------------------------------------------------------------------

class TestWizardUI:

    def test_wizard_opens_on_step_1(self, tk_root):
        """Wizard is created, visible, and starts on step 0 (API Key)."""
        wizard, _, _ = _make_wizard(tk_root)
        assert wizard.winfo_exists()
        assert wizard._step == 0
        wizard.destroy()

    def test_progress_bar_starts_at_zero(self, tk_root):
        wizard, _, _ = _make_wizard(tk_root)
        assert wizard._progress.get() == pytest.approx(0.0)
        wizard.destroy()

    def test_back_button_disabled_on_first_step(self, tk_root):
        wizard, _, _ = _make_wizard(tk_root)
        assert wizard._back_btn.cget("state") == "disabled"
        wizard.destroy()

    def test_back_button_enabled_after_first_step(self, tk_root):
        wizard, _, _ = _make_wizard(tk_root, cookie="dummy_value_for_nav")
        wizard._show_step(1)   # cookie step
        pump(tk_root, 0.1)
        assert wizard._back_btn.cget("state") == "normal"
        wizard.destroy()

    def test_cookie_step_blocked_when_empty(self, tk_root):
        """Next on the cookie step is blocked if the cookie field is empty."""
        wizard, _, _ = _make_wizard(tk_root)
        wizard._show_step(1)
        wizard._cookie_var.set("")
        pump(tk_root, 0.1)
        wizard._next()   # should fail validation
        pump(tk_root, 0.1)
        assert wizard._step == 1, "Should stay on step 1 when cookie is empty"
        wizard.destroy()

    def test_api_key_step_allows_empty(self, tk_root):
        """API key is optional — Next proceeds even when the field is empty."""
        wizard, _, _ = _make_wizard(tk_root)
        assert wizard._step == 0
        wizard._api_key_var.set("")
        wizard._next()
        pump(tk_root, 0.1)
        assert wizard._step == 1, "Should advance to step 1 with empty api_key"
        wizard.destroy()

    def test_finish_button_label_on_last_step(self, tk_root):
        wizard, _, _ = _make_wizard(tk_root)
        wizard._show_step(4)   # last step
        pump(tk_root, 0.1)
        assert "finish" in wizard._next_btn.cget("text").lower()
        wizard.destroy()

    def test_auto_extract_button_exists_on_cookie_step(self, tk_root):
        wizard, _, _ = _make_wizard(tk_root)
        wizard._show_step(1)
        pump(tk_root, 0.1)
        assert hasattr(wizard, "_auto_btn"), "_auto_btn should be created by _step_cookie()"
        assert wizard._auto_btn.winfo_exists()
        wizard.destroy()


# ---------------------------------------------------------------------------
# Suite 2 — Full setup with real login (credentials required)
# ---------------------------------------------------------------------------

class TestWizardSetup:

    @pytest.mark.timeout(60)
    def test_paw_level_detected(self, tk_root, duckdice_cookie, duckdice_api_key):
        """
        Wizard step 3: PAW level is fetched from the real account
        and the Next button becomes enabled within 15 seconds.
        """
        wizard, _, _ = _make_wizard(tk_root,
                                    api_key=duckdice_api_key,
                                    cookie=duckdice_cookie)
        wizard._show_step(2)   # triggers _fetch_paw() in a background thread
        pump(tk_root, 0.3)

        ok = wait_for(tk_root,
                      lambda: wizard._next_btn.cget("state") == "normal",
                      timeout=15.0)
        assert ok, "PAW level was not detected within 15 seconds"
        assert 0 <= wizard._paw <= 5, f"PAW level {wizard._paw} out of range"
        wizard.destroy()

    @pytest.mark.timeout(90)
    def test_complete_5_step_setup(self, tk_root, duckdice_cookie, duckdice_api_key):
        """
        Walk all 5 wizard steps with real credentials:
          1  API Key    → proceeds (optional field)
          2  Cookie     → proceeds with real cookie
          3  PAW Level  → waits for async API call, then proceeds
          4  Currency   → waits for currency list, then proceeds
          5  Target     → sets 20.0, clicks Finish

        Verifies:
          - on_complete callback fires
          - BotConfig has cookie, currency, and target saved
          - PAW level is valid
        """
        wizard, cfg, completed = _make_wizard(tk_root,
                                              api_key=duckdice_api_key,
                                              cookie=duckdice_cookie)
        # ── Step 1: API Key (optional) ─────────────────────────────
        assert wizard._step == 0
        wizard._next()
        pump(tk_root, 0.1)

        # ── Step 2: Cookie ─────────────────────────────────────────
        assert wizard._step == 1
        wizard._next()
        pump(tk_root, 0.2)

        # ── Step 3: PAW detection ──────────────────────────────────
        assert wizard._step == 2
        ok = wait_for(tk_root,
                      lambda: wizard._next_btn.cget("state") == "normal",
                      timeout=15.0)
        assert ok, "PAW level detection timed out"
        paw = wizard._paw
        assert 0 <= paw <= 5, f"Unexpected PAW level: {paw}"
        wizard._next()

        # ── Step 4: Currency (wait for radio buttons to populate) ──
        pump(tk_root, 1.5)
        assert wizard._step == 3
        wizard._next()

        # ── Step 5: Target & Cashout ───────────────────────────────
        pump(tk_root, 0.1)
        assert wizard._step == 4
        wizard._target_var.set("20.0")
        wizard._next()   # Finish — wizard calls _finish() then destroy()
        pump(tk_root, 0.2)

        # ── Assertions ─────────────────────────────────────────────
        assert completed,                          "on_complete callback was not fired"
        assert cfg.get("cookie") == duckdice_cookie, "Cookie not saved to config"
        assert cfg.get("currency"),                "Currency not saved to config"
        assert float(cfg.get("target_amount")) == pytest.approx(20.0)
