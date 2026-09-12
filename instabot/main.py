#!/usr/bin/env python3
"""
instabot — a thin, honest wrapper around the official `instaloader` CLI.

Design goals (per project requirements):
  * Delegate ALL downloading/auth to the official `instaloader` (single source of truth).
  * Support BOTH targets:
        - a profile handler  ->  `instabot someuser`
        - a Reel/post URL    ->  `instabot https://www.instagram.com/reel/Dc9y3JPvmzF/`
  * Use the browser session (`--load-cookies`) to look like a normal human account.
  * Do NOT hammer Instagram: no wrapper-level retry loop. We lean on instaloader's own
    conservative knobs (`--max-connection-attempts`, `--abort-on 429`) so a rate limit
    ABORTS the run instead of retrying (avoids getting the account flagged). A later
    re-run resumes cleanly thanks to `--fast-update`.
  * Download to the folder the tool was called from (CWD) by default.

Why shortcodes and not raw URLs:
  instaloader 4.15 does NOT accept a post/Reel URL as a target (it would raise
  "Invalid username"). The supported single-post form is `instaloader -- -SHORTCODE`.
  We therefore extract the shortcode from the URL you hand us and build that form.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def version_callback(value: bool) -> None:
    """Display version information and exit before any target is required."""
    if value:
        console.print("[bold cyan]instabot v2.0 — official instaloader wrapper (profiles + Reels)[/bold cyan]")
        raise typer.Exit()


# --- Target detection ---------------------------------------------------------
# Matches the short-code segment of the common Instagram post/Reel URL shapes:
#   https://www.instagram.com/reel/<code>/
#   https://www.instagram.com/reels/<code>/
#   https://www.instagram.com/p/<code>/
#   www.instagram.com/reel/<code>   (no scheme, with or without trailing slash)
_REEL_URL = re.compile(r"instagram\.com/(?:reels?|p)/([A-Za-z0-9_-]+)", re.IGNORECASE)


def classify_target(target: str) -> tuple[str, str]:
    """Return (kind, value) where kind is 'post' or 'profile'.

    'post'    -> value is the extracted shortcode
    'profile' -> value is the username / handler

    Disambiguation: a full Reel URL is always a post; a bare word is ALWAYS a
    profile username (we never guess a username such as "novak4i" is a
    shortcode). To target a bare shortcode explicitly, prefix it with '-'
    (instaloader's own convention), e.g. `instabot -DdHNCWghWdE`.
    """
    t = target.strip().rstrip("/")
    m = _REEL_URL.search(t)
    if m:
        return "post", m.group(1)
    if t.startswith(("http://", "https://")):
        raise typer.BadParameter(
            f"Could not extract a Reel/post shortcode from URL: {target!r}. "
            "Use a Reel/post URL like https://www.instagram.com/reel/<code>/"
        )
    # Explicit bare shortcode: only recognized when the user prefixes it with
    # '-' (instaloader's own single-post convention). Instagram usernames cannot
    # start with '-', so this is unambiguous. A bare word WITHOUT the dash is
    # always a profile username — we never guess a username is a shortcode.
    if t.startswith("-") and re.fullmatch(r"-[A-Za-z0-9_-]{4,}", t):
        return "post", t[1:]
    return "profile", t


# --- Command construction -----------------------------------------------------
def build_instaloader_command(
    kind: str,
    value: str,
    browser: str,
    output: Path,
    limit: int | None,
    max_attempts: int,
    abort_on: list[int],
    keep_videos_profile: bool,
) -> list[str]:
    """Build the exact `instaloader` argv for the given target.

    Every flag here is verified to exist in the installed instaloader 4.15.
    """
    cmd = [
        sys.executable, "-m", "instaloader",
        # Browser session (look like a human; not a bot).
        "--load-cookies", browser,
        # Anti-bot / "do not re-attempt":
        #   - N connection attempts (default 1 => no connection-level retry).
        #   - abort on the listed status codes (default 429) => a rate limit
        #     ABORTS the run instead of retrying, bypassing all retry logic.
        "--max-connection-attempts", str(max_attempts),
        "--abort-on", ",".join(str(c) for c in abort_on),
    ]

    if kind == "post":
        # Single Reel/post. Output goes straight into the chosen folder (CWD by default).
        # A Reel is a video -> do NOT pass --no-videos.
        cmd += [
            "--dirname-pattern", str(output),
            "--",
            f"-{value}",  # instaloader single-post form: `-- -SHORTCODE`
        ]
        return cmd

    # Profile (photo archive behaviour, matching the previous tool).
    cmd += [
        "--dirname-pattern", str(output / "{target}"),
        "--fast-update",              # skip already-downloaded; enables clean resume
        "--no-captions",              # keep the folder clean
        "--no-metadata-json",
        "--no-compress-json",
    ]
    if not keep_videos_profile:
        cmd.append("--no-videos")
    if limit is not None:
        cmd += ["--count", str(limit)]
    cmd.append(value)
    return cmd


def _explain_failure(code: int) -> None:
    """Print a helpful, non-scary explanation of a failed download.

    The overwhelming common cause is Instagram's anti-automation, not a bug here.
    We deliberately do NOT retry — re-attempting is exactly what escalates the block.
    """
    console.print()
    console.print(f"[bold red]❌ Download failed (exit code {code}).[/bold red]")
    console.print(
        "[dim]Most likely this is Instagram's anti-automation, not a tool bug:\n"
        "  • 429 Too Many Requests → your session/IP is currently rate-limited.\n"
        "  • 403 Forbidden         → the query was blocked (bot-detection, or the\n"
        "                            Reel is private/deleted/unavailable to you).\n"
        "instabot deliberately did NOT retry — retrying is what makes the block worse.\n\n"
        "[bold]What to do:[/bold]\n"
        "  1. Wait a while (minutes to a few hours) and re-run the SAME command;\n"
        "     --fast-update resumes where it left off, skipping what you already have.\n"
        "  2. Space out downloads — avoid many back-to-back runs.\n"
        "  3. If it persists, your IP or session may be flagged: switch network\n"
        "     (e.g. a mobile hotspot) before trying anything more aggressive.[/dim]"
    )


def _run_or_print(cmd: list[str], dry_run: bool) -> int:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]\n")
    if dry_run:
        console.print("[yellow]--print-cmd: not executing.[/yellow]")
        return 0
    try:
        # check=False: we surface instaloader's own exit code. We deliberately do NOT
        # retry here — re-attempting on failure is exactly what we are avoiding (bot flagging).
        result = subprocess.run(cmd)
        code = result.returncode
        if code != 0:
            _explain_failure(code)
        return code
    except FileNotFoundError:
        console.print("[bold red]❌ Could not find the Python/instaloader executable.[/bold red]")
        return 127


def main(
    target: str | None = typer.Argument(
        None,
        help="Instagram profile handler (e.g. `someuser`) OR a Reel/post URL "
             "(e.g. https://www.instagram.com/reel/Dc9y3JPvmzF/).",
    ),
    browser: str = typer.Option(
        "chrome", "--browser", "-b",
        help="Browser to import the Instagram session cookies from "
             "(chrome|firefox|edge|safari|brave|opera|vivaldi).",
    ),
    output: Path = typer.Option(
        Path.cwd(), "--output", "-o",
        help="Folder to download into. Defaults to the current working directory.",
    ),
    limit: int | None = typer.Option(
        None, "--limit", "-c",
        help="Profiles only: max number of posts to download (maps to instaloader --count).",
    ),
    videos: bool = typer.Option(
        False, "--videos/--no-videos",
        help="Profiles only: also download videos (default: skip videos for a clean photo archive). "
             "Reels always download their video.",
    ),
    max_attempts: int = typer.Option(
        1, "--max-attempts",
        help="Connection attempts before aborting (default 1 = no retry; raise for flaky links).",
    ),
    abort_on: str = typer.Option(
        "429", "--abort-on",
        help="Comma-separated HTTP status codes that ABORT the run, bypassing all retry logic "
             "(default 429 = rate limit).",
    ),
    print_cmd: bool = typer.Option(
        False, "--print-cmd",
        help="Print the exact instaloader command without executing it (dry run).",
    ),
    version: bool = typer.Option(
        False, "--version", "-v", callback=version_callback,
        help="Show version and exit.",
    ),
) -> None:
    """Download an Instagram profile, or a single Reel/post, via the official instaloader.

    Uses your browser's Instagram session (no bot-looking requests) and is tuned so a
    rate limit ABORTS the run instead of retrying — protecting the account from being
    flagged. Re-run later to resume; `--fast-update` skips what you already have.
    """
    if target is None:
        console.print("[yellow]Provide a profile handler or a Reel/post URL.[/yellow]")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  instabot someuser[/dim]")
        console.print("[dim]  instabot https://www.instagram.com/reel/Dc9y3JPvmzF/[/dim]")
        raise typer.Exit(code=2)

    try:
        kind, value = classify_target(target)
    except typer.BadParameter as e:
        raise typer.BadParameter(str(e))

    abort_codes: list[int] = []
    for chunk in abort_on.split(","):
        chunk = chunk.strip()
        if chunk:
            try:
                abort_codes.append(int(chunk))
            except ValueError:
                raise typer.BadParameter(f"--abort-on value is not an integer: {chunk!r}")
    if not abort_codes:
        abort_codes = [429]

    if not output.is_dir():
        output.mkdir(parents=True, exist_ok=True)

    cmd = build_instaloader_command(
        kind=kind,
        value=value,
        browser=browser,
        output=output,
        limit=limit,
        max_attempts=max_attempts,
        abort_on=abort_codes,
        keep_videos_profile=videos,
    )

    if kind == "post":
        console.print(Panel(
            f"📸 [bold]instabot[/bold] → [bold green]Reel/Post[/bold green]\n"
            f"Shortcode: [cyan]{value}[/cyan]\n"
            f"Dest: [blue]{output}[/blue]\n"
            f"Session: [dim]{browser} cookies[/dim] | Anti-bot: [dim]{max_attempts} attempt(s), "
            f"abort-on {abort_codes}[/dim]",
            style="purple",
        ))
    else:
        limit_str = f" | Limit: [dim]{limit}[/dim]" if limit else ""
        console.print(Panel(
            f"📸 [bold]instabot[/bold] → [bold green]Profile[/bold green]\n"
            f"Target: [cyan]@{value}[/cyan]\n"
            f"Dest: [blue]{output / value}[/blue]\n"
            f"Session: [dim]{browser} cookies[/dim] | Anti-bot: [dim]{max_attempts} attempt(s), "
            f"abort-on {abort_codes}[/dim]{limit_str}",
            style="purple",
        ))

    raise typer.Exit(code=_run_or_print(cmd, dry_run=print_cmd))


if __name__ == "__main__":
    typer.run(main)
