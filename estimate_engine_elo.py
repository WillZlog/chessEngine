from __future__ import annotations

import argparse
import math
import random
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chess
import chess.engine
import chess.pgn

OPENINGS: list[list[str]] = [
    [],
    ["e2e4", "e7e5"],
    ["e2e4", "c7c5"],
    ["e2e4", "e7e6"],
    ["e2e4", "c7c6"],
    ["d2d4", "d7d5"],
    ["d2d4", "g8f6", "c2c4", "e7e6"],
    ["d2d4", "g8f6", "c2c4", "g7g6"],
    ["c2c4", "e7e5"],
    ["g1f3", "d7d5", "g2g3"],
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["e2e4", "c7c5", "g1f3", "d7d6"],
]


@dataclass
class MatchResult:
    opponent_elo: int
    wins: int = 0
    draws: int = 0
    losses: int = 0
    engine_errors: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float:
        if self.games == 0:
            return 0.0
        return (self.wins + 0.5 * self.draws) / self.games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate a UCI chess engine's Elo against limited-strength Stockfish."
    )
    parser.add_argument(
        "--engine",
        default="./main",
        help="Path to your UCI engine binary (default: ./main)",
    )
    parser.add_argument(
        "--engine-arg",
        action="append",
        default=["--uci"],
        help="Argument passed to your engine. May be repeated (default: --uci)",
    )
    parser.add_argument(
        "--stockfish",
        default=shutil.which("stockfish") or "/opt/homebrew/bin/stockfish",
        help="Path to Stockfish",
    )
    parser.add_argument(
        "--levels",
        nargs="+",
        type=int,
        default=[1320, 1450, 1600, 1750, 1900],
        help="Stockfish Elo levels to test",
    )
    parser.add_argument(
        "--games-per-level",
        type=int,
        default=20,
        help="Games per Stockfish level; rounded up to an even number (default: 20)",
    )
    parser.add_argument(
        "--engine-depth",
        type=int,
        default=4,
        help="Search depth for your engine (default: 4)",
    )
    parser.add_argument(
        "--stockfish-time",
        type=float,
        default=0.10,
        help="Stockfish thinking time per move in seconds (default: 0.10)",
    )
    parser.add_argument(
        "--max-plies",
        type=int,
        default=300,
        help="Draw games that exceed this many half-moves (default: 300)",
    )
    parser.add_argument(
        "--pgn",
        default="elo_test_games.pgn",
        help="PGN output path (default: elo_test_games.pgn)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260730,
        help="Opening shuffle seed",
    )
    return parser.parse_args()


def validate_paths(args: argparse.Namespace) -> None:
    engine_path = Path(args.engine)
    if not engine_path.exists():
        raise SystemExit(f"Engine not found: {engine_path}")
    if not engine_path.is_file():
        raise SystemExit(f"Engine path is not a file: {engine_path}")

    stockfish_path = Path(args.stockfish)
    if not stockfish_path.exists():
        raise SystemExit(
            "Stockfish not found. Install it with `brew install stockfish`, "
            "or pass --stockfish /path/to/stockfish"
        )


def start_engines(args: argparse.Namespace) -> tuple[chess.engine.SimpleEngine, chess.engine.SimpleEngine]:
    our_command = [str(Path(args.engine).resolve()), *args.engine_arg]
    stockfish_command = str(Path(args.stockfish).resolve())

    print("Starting your engine:", " ".join(our_command))
    our_engine = chess.engine.SimpleEngine.popen_uci(our_command, timeout=15.0)

    try:
        print("Starting Stockfish:", stockfish_command)
        stockfish = chess.engine.SimpleEngine.popen_uci(stockfish_command, timeout=15.0)
    except Exception:
        our_engine.quit()
        raise

    stockfish.configure(
        {
            "UCI_LimitStrength": True,
            "Threads": 1,
            "Hash": 64,
        }
    )
    return our_engine, stockfish


def apply_opening(board: chess.Board, moves: list[str]) -> None:
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"Opening contains illegal move {uci}")
        board.push(move)


def safe_play(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    limit: chess.engine.Limit,
) -> chess.Move:
    result = engine.play(board, limit)
    if result.move is None:
        raise RuntimeError("Engine returned no move")
    if result.move not in board.legal_moves:
        raise RuntimeError(f"Engine returned illegal move: {result.move.uci()}")
    return result.move


def play_game(
    our_engine: chess.engine.SimpleEngine,
    stockfish: chess.engine.SimpleEngine,
    our_color: chess.Color,
    opponent_elo: int,
    opening: list[str],
    engine_depth: int,
    stockfish_time: float,
    max_plies: int,
) -> tuple[str, chess.pgn.Game, Optional[str]]:
    board = chess.Board()
    apply_opening(board, opening)

    game = chess.pgn.Game()
    game.headers["Event"] = "Local Elo Estimate"
    game.headers["White"] = "YourEngine" if our_color == chess.WHITE else f"Stockfish-{opponent_elo}"
    game.headers["Black"] = f"Stockfish-{opponent_elo}" if our_color == chess.WHITE else "YourEngine"
    game.headers["StockfishElo"] = str(opponent_elo)
    game.headers["EngineDepth"] = str(engine_depth)
    game.headers["OpeningUCI"] = " ".join(opening) if opening else "startpos"

    node = game
    # Record the opening in the PGN.
    opening_board = chess.Board()
    for uci in opening:
        move = chess.Move.from_uci(uci)
        node = node.add_variation(move)
        opening_board.push(move)

    stockfish.configure({"UCI_Elo": opponent_elo})
    error: Optional[str] = None

    while not board.is_game_over(claim_draw=True) and board.ply() < max_plies:
        try:
            if board.turn == our_color:
                move = safe_play(
                    our_engine,
                    board,
                    chess.engine.Limit(depth=engine_depth),
                )
            else:
                move = safe_play(
                    stockfish,
                    board,
                    chess.engine.Limit(time=stockfish_time),
                )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            # The engine that failed loses.
            result = "0-1" if board.turn == chess.WHITE else "1-0"
            game.headers["Termination"] = "engine error"
            game.headers["EngineError"] = error
            game.headers["Result"] = result
            return result, game, error

        board.push(move)
        node = node.add_variation(move)

    if board.is_game_over(claim_draw=True):
        result = board.result(claim_draw=True)
        game.headers["Termination"] = board.outcome(claim_draw=True).termination.name
    else:
        result = "1/2-1/2"
        game.headers["Termination"] = f"max plies ({max_plies})"

    game.headers["Result"] = result
    return result, game, error


def score_for_our_engine(result: str, our_color: chess.Color) -> float:
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if our_color == chess.WHITE else 0.0
    if result == "0-1":
        return 1.0 if our_color == chess.BLACK else 0.0
    raise ValueError(f"Unknown result: {result}")


def update_result(
    match: MatchResult,
    game_result: str,
    our_color: chess.Color,
    error: Optional[str],
) -> None:
    score = score_for_our_engine(game_result, our_color)
    if score == 1.0:
        match.wins += 1
    elif score == 0.5:
        match.draws += 1
    else:
        match.losses += 1
    if error:
        match.engine_errors += 1


def expected_score(player_elo: float, opponent_elo: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((opponent_elo - player_elo) / 400.0))


def log_likelihood(candidate_elo: float, results: list[MatchResult]) -> float:
    total = 0.0
    epsilon = 1e-12
    for result in results:
        if result.games == 0:
            continue
        p = min(max(expected_score(candidate_elo, result.opponent_elo), epsilon), 1.0 - epsilon)
        # Treat draws as half a win and half a loss for a simple logistic estimate.
        successes = result.wins + 0.5 * result.draws
        failures = result.losses + 0.5 * result.draws
        total += successes * math.log(p) + failures * math.log(1.0 - p)
    return total


def estimate_elo(results: list[MatchResult]) -> tuple[float, float, float]:
    grid = [float(r) for r in range(600, 3001)]
    likelihoods = [log_likelihood(r, results) for r in grid]
    best_index = max(range(len(grid)), key=lambda i: likelihoods[i])
    best_elo = grid[best_index]
    best_ll = likelihoods[best_index]

    # Approximate 95% likelihood interval: 2*delta log-likelihood <= 3.84.
    cutoff = best_ll - 1.92
    allowed = [elo for elo, ll in zip(grid, likelihoods) if ll >= cutoff]
    low = min(allowed) if allowed else best_elo
    high = max(allowed) if allowed else best_elo
    return best_elo, low, high


def print_summary(results: list[MatchResult]) -> None:
    print("\nResults by Stockfish setting")
    print("-" * 64)
    print(f"{'SF Elo':>7}  {'W':>4} {'D':>4} {'L':>4}  {'Score':>8}  {'Errors':>6}")
    for result in results:
        print(
            f"{result.opponent_elo:>7}  "
            f"{result.wins:>4} {result.draws:>4} {result.losses:>4}  "
            f"{100.0 * result.score:>7.1f}%  "
            f"{result.engine_errors:>6}"
        )

    estimate, low, high = estimate_elo(results)
    total_games = sum(r.games for r in results)
    total_errors = sum(r.engine_errors for r in results)

    print("-" * 64)
    print(f"Estimated engine Elo: {estimate:.0f}")
    print(f"Approximate 95% interval: {low:.0f} to {high:.0f}")
    print(f"Games: {total_games}; engine-error games: {total_errors}")


def main() -> int:
    args = parse_args()
    validate_paths(args)

    if args.games_per_level < 2:
        raise SystemExit("--games-per-level must be at least 2")
    if args.games_per_level % 2:
        args.games_per_level += 1
        print(f"Rounded games per level up to {args.games_per_level} for color pairs.")

    randomizer = random.Random(args.seed)
    openings = OPENINGS.copy()
    randomizer.shuffle(openings)

    results: list[MatchResult] = []
    pgn_path = Path(args.pgn)

    our_engine: Optional[chess.engine.SimpleEngine] = None
    stockfish: Optional[chess.engine.SimpleEngine] = None

    try:
        our_engine, stockfish = start_engines(args)

        with pgn_path.open("w", encoding="utf-8") as pgn_file:
            game_number = 0

            for opponent_elo in args.levels:
                match = MatchResult(opponent_elo=opponent_elo)
                results.append(match)
                pair_count = args.games_per_level // 2

                print(f"\nTesting against Stockfish UCI_Elo={opponent_elo}")

                for pair_index in range(pair_count):
                    opening = openings[pair_index % len(openings)]

                    for our_color in (chess.WHITE, chess.BLACK):
                        game_number += 1
                        color_name = "White" if our_color == chess.WHITE else "Black"
                        print(
                            f"Game {game_number}: your engine as {color_name}, "
                            f"opening {pair_index + 1}/{pair_count}",
                            flush=True,
                        )

                        result, game, error = play_game(
                            our_engine=our_engine,
                            stockfish=stockfish,
                            our_color=our_color,
                            opponent_elo=opponent_elo,
                            opening=opening,
                            engine_depth=args.engine_depth,
                            stockfish_time=args.stockfish_time,
                            max_plies=args.max_plies,
                        )

                        update_result(match, result, our_color, error)
                        print(game, file=pgn_file, end="\n\n")
                        pgn_file.flush()

                        score = score_for_our_engine(result, our_color)
                        label = "win" if score == 1.0 else "draw" if score == 0.5 else "loss"
                        suffix = f" — {error}" if error else ""
                        print(f"  Result: {result} ({label}){suffix}")

                print(
                    f"Level {opponent_elo}: "
                    f"{match.wins}W {match.draws}D {match.losses}L "
                    f"({100.0 * match.score:.1f}%)"
                )

        print_summary(results)
        print(f"\nPGN saved to: {pgn_path.resolve()}")
        return 0

    except KeyboardInterrupt:
        print("\nStopped by user.")
        if results:
            print_summary(results)
        return 130
    finally:
        for engine in (our_engine, stockfish):
            if engine is not None:
                try:
                    engine.quit()
                except Exception:
                    try:
                        engine.close()
                    except Exception:
                        pass


if __name__ == "__main__":
    raise SystemExit(main())
