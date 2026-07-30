#!/usr/bin/env python3
"""
Minimal Lichess BOT wrapper for a UCI chess engine.

Environment variables:
    LICHESS_TOKEN   Required Lichess BOT API token
    ENGINE_PATH     Engine executable path (default: ./main)
    ENGINE_DEPTH    Search depth (default: 4)
    ENGINE_ARGS     Optional additional engine arguments

Example:
    export LICHESS_TOKEN="lip_..."
    export ENGINE_PATH="./main"
    export ENGINE_DEPTH="4"

    python3 lichess_bot.py

Requirements:
    pip install requests
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import threading
import time
from typing import Any, Iterator, Optional

import requests

LICHESS_API = "https://lichess.org"

ENGINE_PATH = os.environ.get("ENGINE_PATH", "./main")
ENGINE_ARGS = shlex.split(os.environ.get("ENGINE_ARGS", "--uci"))
SEARCH_DEPTH = int(os.environ.get("ENGINE_DEPTH", "4"))

TOKEN = os.environ.get("LICHESS_TOKEN")

CONNECT_TIMEOUT = 10
STREAM_READ_TIMEOUT = 30
REQUEST_TIMEOUT = 15


if not TOKEN:
    print(
        "Error: LICHESS_TOKEN environment variable is not set.",
        file=sys.stderr,
    )
    sys.exit(1)


def create_session() -> requests.Session:
    """Create an authenticated HTTP session."""
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/x-ndjson, application/json",
            "User-Agent": "minimal-uci-lichess-bot/1.0",
        }
    )
    return session


MAIN_SESSION = create_session()


def iter_ndjson(response: requests.Response) -> Iterator[dict[str, Any]]:
    """
    Parse a Lichess NDJSON response.

    Lichess streaming endpoints return one JSON object per line.
    Empty lines are keep-alive messages and should be ignored.
    """
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue

        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace").strip()
        else:
            line = str(raw_line).strip()

        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                f"Could not parse stream line: {exc}; line={line!r}",
                file=sys.stderr,
            )
            continue

        if isinstance(event, dict):
            yield event


def read_bot_account_id() -> Optional[str]:
    """Return the authenticated bot account's lowercase Lichess ID."""
    try:
        response = MAIN_SESSION.get(
            f"{LICHESS_API}/api/account",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to get account information: {exc}", file=sys.stderr)
        return None

    data = response.json()
    account_id = data.get("id")

    if not isinstance(account_id, str):
        print("Account response did not contain an ID.", file=sys.stderr)
        return None

    return account_id.lower()


def accept_challenge(challenge_id: str) -> bool:
    """Accept an incoming Lichess challenge."""
    try:
        response = MAIN_SESSION.post(
            f"{LICHESS_API}/api/challenge/{challenge_id}/accept",
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"Could not accept challenge {challenge_id}: {exc}")
        return False

    if response.status_code == 200:
        return True

    print(
        f"Could not accept challenge {challenge_id}: "
        f"{response.status_code} {response.text}"
    )
    return False


def decline_challenge(
    challenge_id: str,
    reason: str = "generic",
) -> bool:
    """Decline an incoming challenge."""
    try:
        response = MAIN_SESSION.post(
            f"{LICHESS_API}/api/challenge/{challenge_id}/decline",
            data={"reason": reason},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"Could not decline challenge {challenge_id}: {exc}")
        return False

    return response.status_code == 200


def post_move(game_id: str, uci_move: str) -> bool:
    """Submit a UCI move to Lichess."""
    try:
        response = MAIN_SESSION.post(
            f"{LICHESS_API}/api/bot/game/{game_id}/move/{uci_move}",
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"Network error while posting {uci_move} " f"in game {game_id}: {exc}")
        return False

    if response.status_code in (200, 201):
        return True

    print(
        f"Failed to post move {uci_move} in game {game_id}: "
        f"{response.status_code} {response.text}"
    )
    return False


def write_engine(
    engine: subprocess.Popen[str],
    command: str,
) -> None:
    """Send one command to the UCI engine."""
    if engine.stdin is None:
        raise RuntimeError("Engine stdin is unavailable.")

    if engine.poll() is not None:
        raise RuntimeError(f"Engine exited with status {engine.returncode}.")

    engine.stdin.write(command + "\n")
    engine.stdin.flush()


def wait_for_engine_output(
    engine: subprocess.Popen[str],
    expected: str,
) -> None:
    """Read engine output until a specific UCI response is received."""
    if engine.stdout is None:
        raise RuntimeError("Engine stdout is unavailable.")

    while True:
        line = engine.stdout.readline()

        if line == "":
            stderr_output = ""

            if engine.stderr is not None:
                try:
                    stderr_output = engine.stderr.read().strip()
                except Exception:
                    pass

            message = f"Engine terminated while waiting for {expected!r}."

            if stderr_output:
                message += f" Engine stderr: {stderr_output}"

            raise RuntimeError(message)

        line = line.strip()

        if line:
            print(f"[engine] {line}")

        if line == expected:
            return


def spawn_engine() -> subprocess.Popen[str]:
    """Start and initialize a UCI engine."""
    command = [ENGINE_PATH, *ENGINE_ARGS]

    print(f"Starting engine: {shlex.join(command)}")

    try:
        engine = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Engine executable was not found: {ENGINE_PATH}") from exc
    except PermissionError as exc:
        raise RuntimeError(
            f"Engine is not executable: {ENGINE_PATH}. "
            f"Run: chmod +x {shlex.quote(ENGINE_PATH)}"
        ) from exc

    try:
        write_engine(engine, "uci")
        wait_for_engine_output(engine, "uciok")

        write_engine(engine, "isready")
        wait_for_engine_output(engine, "readyok")

        write_engine(engine, "ucinewgame")

        write_engine(engine, "isready")
        wait_for_engine_output(engine, "readyok")
    except Exception:
        stop_engine(engine)
        raise

    return engine


def stop_engine(engine: subprocess.Popen[str]) -> None:
    """Gracefully stop an engine process, then force it if necessary."""
    if engine.poll() is not None:
        return

    try:
        write_engine(engine, "quit")
        engine.wait(timeout=2)
        return
    except Exception:
        pass

    try:
        engine.terminate()
        engine.wait(timeout=2)
        return
    except Exception:
        pass

    try:
        engine.kill()
    except Exception:
        pass


def engine_get_bestmove(
    engine: subprocess.Popen[str],
    moves: list[str],
    depth: int,
    initial_fen: Optional[str] = None,
) -> Optional[str]:
    """Ask the engine for its best move in the supplied position."""
    if engine.stdout is None:
        raise RuntimeError("Engine stdout is unavailable.")

    if initial_fen and initial_fen != "startpos":
        position_command = f"position fen {initial_fen}"
    else:
        position_command = "position startpos"

    if moves:
        position_command += " moves " + " ".join(moves)

    write_engine(engine, position_command)
    write_engine(engine, f"go depth {depth}")

    while True:
        line = engine.stdout.readline()

        if line == "":
            print("Engine exited before returning bestmove.")
            return None

        line = line.strip()

        if line:
            print(f"[engine] {line}")

        if not line.startswith("bestmove"):
            continue

        parts = line.split()

        if len(parts) < 2:
            return None

        move = parts[1]

        if move in {"(none)", "0000"}:
            return None

        return move


def player_id(player: Any) -> Optional[str]:
    """Extract a lowercase Lichess ID from a player object."""
    if not isinstance(player, dict):
        return None

    value = player.get("id")

    if isinstance(value, str):
        return value.lower()

    # Depending on the event, user information can be nested.
    user = player.get("user")

    if isinstance(user, dict):
        value = user.get("id")

        if isinstance(value, str):
            return value.lower()

    return None


def determine_bot_color(
    event: dict[str, Any],
    bot_id: str,
) -> Optional[str]:
    """Determine whether the bot is White or Black."""
    white_id = player_id(event.get("white"))
    black_id = player_id(event.get("black"))

    if white_id == bot_id:
        return "white"

    if black_id == bot_id:
        return "black"

    return None


def is_our_turn(bot_color: str, move_count: int) -> bool:
    """Return whether the supplied ply count means it is our turn."""
    side_to_move = "white" if move_count % 2 == 0 else "black"
    return side_to_move == bot_color


def extract_initial_fen(event: dict[str, Any]) -> Optional[str]:
    """Extract a nonstandard initial FEN from gameFull."""
    initial_fen = event.get("initialFen")

    if not isinstance(initial_fen, str):
        return None

    if initial_fen == "startpos":
        return None

    return initial_fen


def handle_game(game_id: str, bot_id: str) -> None:
    """Stream and play one Lichess game."""
    print(f"[{game_id}] Starting game handler.")

    engine: Optional[subprocess.Popen[str]] = None
    session = create_session()

    bot_color: Optional[str] = None
    initial_fen: Optional[str] = None

    # Prevent playing twice when Lichess sends the same position again.
    last_attempted_ply = -1

    try:
        stream_url = f"{LICHESS_API}/api/bot/game/stream/{game_id}"

        with session.get(
            stream_url,
            stream=True,
            timeout=(CONNECT_TIMEOUT, STREAM_READ_TIMEOUT),
        ) as response:
            if response.status_code != 200:
                print(
                    f"[{game_id}] Failed to open game stream: "
                    f"{response.status_code} {response.text}"
                )
                return

            for event in iter_ndjson(response):
                event_type = event.get("type")

                if event_type == "gameFull":
                    bot_color = determine_bot_color(event, bot_id)

                    if bot_color is None:
                        print(
                            f"[{game_id}] Could not determine bot color. "
                            f"Bot ID: {bot_id}"
                        )
                        return

                    initial_fen = extract_initial_fen(event)

                    state = event.get("state", {})

                    if not isinstance(state, dict):
                        print(f"[{game_id}] Invalid initial game state.")
                        return

                elif event_type == "gameState":
                    # gameState itself is the state object.
                    state = event

                elif event_type in {
                    "chatLine",
                    "opponentGone",
                }:
                    continue

                else:
                    print(f"[{game_id}] Ignoring event type: " f"{event_type!r}")
                    continue

                status = state.get("status", "started")

                if status != "started":
                    winner = state.get("winner")
                    print(
                        f"[{game_id}] Game ended. " f"Status={status}, winner={winner}"
                    )
                    break

                if bot_color is None:
                    continue

                moves_value = state.get("moves", "")

                if isinstance(moves_value, str) and moves_value.strip():
                    moves = moves_value.split()
                else:
                    moves = []

                current_ply = len(moves)

                if not is_our_turn(bot_color, current_ply):
                    continue

                if current_ply == last_attempted_ply:
                    continue

                last_attempted_ply = current_ply

                if engine is None:
                    try:
                        engine = spawn_engine()
                    except Exception as exc:
                        print(f"[{game_id}] Failed to start engine: {exc}")
                        return

                try:
                    best_move = engine_get_bestmove(
                        engine=engine,
                        moves=moves,
                        depth=SEARCH_DEPTH,
                        initial_fen=initial_fen,
                    )
                except Exception as exc:
                    print(f"[{game_id}] Engine search failed: {exc}")
                    return

                if best_move is None:
                    print(f"[{game_id}] Engine did not return a move.")
                    continue

                print(f"[{game_id}] Playing {best_move} " f"at ply {current_ply}.")

                if not post_move(game_id, best_move):
                    print(f"[{game_id}] Lichess rejected {best_move}.")

    except requests.exceptions.ReadTimeout:
        print(f"[{game_id}] Game stream timed out.")
    except requests.RequestException as exc:
        print(f"[{game_id}] Game stream network error: {exc}")
    except Exception as exc:
        print(f"[{game_id}] Unexpected game handler error: {exc}")
    finally:
        if engine is not None:
            stop_engine(engine)

        session.close()
        print(f"[{game_id}] Game handler stopped.")


def should_accept_challenge(challenge: dict[str, Any]) -> bool:
    """
    Only accept standard chess challenges.

    This engine wrapper does not assume support for variants such as
    antichess, atomic, crazyhouse, or Chess960.
    """
    variant = challenge.get("variant", {})

    if not isinstance(variant, dict):
        return False

    variant_key = variant.get("key")
    return variant_key == "standard"


def event_listener(bot_id: str) -> None:
    """Continuously listen for challenges and game starts."""
    stream_url = f"{LICHESS_API}/api/stream/event"

    while True:
        session = create_session()

        try:
            print("Connecting to Lichess event stream...")

            with session.get(
                stream_url,
                stream=True,
                timeout=(CONNECT_TIMEOUT, STREAM_READ_TIMEOUT),
            ) as response:
                if response.status_code != 200:
                    print(
                        "Failed to connect to event stream: "
                        f"{response.status_code} {response.text}"
                    )
                    time.sleep(5)
                    continue

                print("Connected to Lichess event stream.")

                for event in iter_ndjson(response):
                    event_type = event.get("type")

                    print("[event] " + json.dumps(event, separators=(",", ":")))

                    if event_type == "challenge":
                        challenge = event.get("challenge", {})

                        if not isinstance(challenge, dict):
                            continue

                        challenge_id = challenge.get("id")

                        if not isinstance(challenge_id, str):
                            continue

                        if should_accept_challenge(challenge):
                            print(f"Accepting challenge {challenge_id}.")
                            accept_challenge(challenge_id)
                        else:
                            print(
                                f"Declining unsupported challenge " f"{challenge_id}."
                            )
                            decline_challenge(
                                challenge_id,
                                reason="variant",
                            )

                    elif event_type == "gameStart":
                        game = event.get("game", {})

                        if not isinstance(game, dict):
                            continue

                        game_id = game.get("id")

                        if not isinstance(game_id, str):
                            continue

                        print(f"Game started: {game_id}")

                        thread = threading.Thread(
                            target=handle_game,
                            args=(game_id, bot_id),
                            name=f"game-{game_id}",
                            daemon=True,
                        )
                        thread.start()

                    elif event_type == "gameFinish":
                        game = event.get("game", {})

                        if isinstance(game, dict):
                            print(f"Game finished: {game.get('id')}")

        except requests.exceptions.ReadTimeout:
            print("Event stream became inactive; reconnecting...")
            time.sleep(1)

        except requests.RequestException as exc:
            print(f"Event stream network error: {exc}; reconnecting...")
            time.sleep(5)

        except Exception as exc:
            print(f"Unexpected event listener error: {exc}; " "reconnecting...")
            time.sleep(5)

        finally:
            session.close()


def main() -> None:
    bot_id = read_bot_account_id()

    if bot_id is None:
        print(
            "Unable to determine the bot account ID.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.isfile(ENGINE_PATH):
        print(
            f"Engine does not exist at {ENGINE_PATH!r}.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.access(ENGINE_PATH, os.X_OK):
        print(
            f"Engine is not executable. Run:\n" f"chmod +x {shlex.quote(ENGINE_PATH)}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Bot account ID: {bot_id}")
    print(f"Engine path: {ENGINE_PATH}")
    print(f"Search depth: {SEARCH_DEPTH}")

    try:
        event_listener(bot_id)
    except KeyboardInterrupt:
        print("\nStopping bot.")


if __name__ == "__main__":
    main()
