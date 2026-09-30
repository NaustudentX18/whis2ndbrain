# Accessibility checklist (review shell)

Working checklist for WB-051 preparation against the Python-served review
shell (`server/pwa.py`), per lane C3 of the v1 swarm plan. Statuses here are
preparation evidence only — WB acceptance stays with the owner's board and
its evidence+reviewer rule.

## Automated (runs in CI)

Third Chromium e2e scenario: `tests/e2e/test_browser_review.py::test_accessibility_baseline_320_focus_contrast`

| Dimension | Check | Standard |
| --- | --- | --- |
| Reflow at 320 px | Login page and review shell render with no horizontal scrolling at 320 CSS px | WCAG 1.4.10 |
| 200 % zoom (equivalent) | 320 px is the practical reflow equivalent of 200 % zoom on a 640 px baseline; asserted by the same 320 px scenario | WCAG 1.4.4 (viewport form) |
| Keyboard focus | First `Tab` on the login page lands on the token input; the focused control shows a ≥1 px non-`none` outline (the shell ships a 2 px accent `:focus-visible` ring) | WCAG 2.4.7 |
| Text contrast | AA (≥4.5:1) computed from real rendered styles for headings, labels, body text, buttons and links on both pages | WCAG 1.4.3 |
| Control names | Every `button`, `a[href]`, `input` and `[role=button]` has a non-empty accessible name (text, `aria-label`, `title` or value) | WCAG 4.1.2 |

Run locally (needs `chromium` + `chromedriver` on PATH):

```
.venv/bin/python -m unittest tests.e2e.test_browser_review
```

## Manual (headless Chromium cannot honestly prove these)

- [ ] Full keyboard-only walkthrough of every flow: login → feed → search →
      edit (modal) → delete/restore → trash view → logout, no pointer.
- [ ] Screen-reader pass on a real browser/screen-reader pair (Orca or
      NVDA): landmarks, headings, audio controls, modal focus trapping and
      announcements.
- [ ] True 200 % browser/OS zoom on a desktop viewport (the 320 px check is
      the reflow equivalent, not the zoom proof).
- [ ] `prefers-reduced-motion` behaviour if animations are added later.
- [ ] Real-phone qualification (install, reopen, offline) — WB-051 proper on
      the owner's S25; deferred with the hardware/real-phone gates.

## Known limits

- Automated checks run on desktop Chromium headless only; they cover the two
  pages the shell serves today (login + review). New surfaces must extend
  the scenario.
- Contrast is asserted for the shell's semantic text and controls; purely
  decorative or disabled elements are out of scope.
