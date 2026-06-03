#!/usr/bin/env python3
# =============================================================================
# word_game.py — Main game engine
#
# Structure:
#   ScoreManager  — handles scoring, high scores, and persistent statistics
#   WordGame      — core game state, hint generation, similarity scoring
#   main_menu()   — top-level navigation
#   play_game()   — one full round of the guessing game
#   display_statistics() — summary screen
# =============================================================================

import os
import sys
import json
import time
import random
import string

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
except ImportError:
    # Colorama not installed — define no-op wrappers so the game still runs.
    print("colorama not found. Run: pip install colorama")
    class _Noop:
        def __getattr__(self, name):
            return ""
    Fore = Back = Style = _Noop()

from word_database import get_words_by_difficulty


# ─── paths ────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
SCORES_FILE     = os.path.join(BASE_DIR, "scores.json")
STATISTICS_FILE = os.path.join(BASE_DIR, "statistics.json")


# =============================================================================
# UTILITY HELPERS
# =============================================================================

def clear_screen():
    """Wipe the terminal to keep things tidy."""
    os.system("cls" if os.name == "nt" else "clear")


def loading_animation(message: str = "Loading", duration: float = 1.5):
    """
    Show a simple spinner for *duration* seconds.
    Keeps the experience feeling polished.
    """
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    deadline = time.time() + duration
    i = 0
    while time.time() < deadline:
        sys.stdout.write(f"\r{Fore.CYAN}{frames[i % len(frames)]}  {message}...{Style.RESET_ALL}")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1
    # Clean up the spinner line
    sys.stdout.write("\r" + " " * (len(message) + 12) + "\r")
    sys.stdout.flush()


def slow_print(text: str, delay: float = 0.025):
    """Print text character by character for dramatic effect."""
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def print_divider(char: str = "─", width: int = 60, color=None):
    """Print a horizontal rule."""
    line = char * width
    if color:
        print(color + line + Style.RESET_ALL)
    else:
        print(line)


# =============================================================================
# ASCII ART TITLE
# =============================================================================

ASCII_TITLE = f"""
{Fore.YELLOW}
 ██╗    ██╗ ██████╗ ██████╗ ██████╗      ██████╗ ██╗   ██╗███████╗███████╗███████╗
 ██║    ██║██╔═══██╗██╔══██╗██╔══██╗    ██╔════╝ ██║   ██║██╔════╝██╔════╝██╔════╝
 ██║ █╗ ██║██║   ██║██████╔╝██║  ██║    ██║  ███╗██║   ██║█████╗  ███████╗███████╗
 ██║███╗██║██║   ██║██╔══██╗██║  ██║    ██║   ██║██║   ██║██╔══╝  ╚════██║╚════██║
 ╚███╔███╔╝╚██████╔╝██║  ██║██████╔╝    ╚██████╔╝╚██████╔╝███████╗███████║███████║
  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═════╝      ╚═════╝  ╚═════╝ ╚══════╝╚══════╝╚══════╝
{Style.RESET_ALL}"""


# =============================================================================
# SCORE MANAGER
# =============================================================================

class ScoreManager:
    """
    Persists scores and statistics to JSON files so they survive between runs.

    Files created:
        scores.json      — per-difficulty leaderboard entries
        statistics.json  — aggregate game statistics
    """

    def __init__(self):
        self.scores     = self._load(SCORES_FILE,     default={"easy": [], "medium": [], "hard": []})
        self.statistics = self._load(STATISTICS_FILE, default={
            "total_games":  0,
            "total_wins":   0,
            "total_losses": 0,
            "best_score":   0,
            "total_score":  0,
            "easy_wins":    0,
            "medium_wins":  0,
            "hard_wins":    0,
        })

    # ── persistence ──────────────────────────────────────────────────────────

    @staticmethod
    def _load(path: str, default: dict) -> dict:
        """Read JSON file, fall back to *default* if missing or corrupt."""
        if os.path.exists(path):
            try:
                with open(path, "r") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, IOError):
                pass
        return default

    @staticmethod
    def _save(path: str, data: dict):
        """Write *data* as pretty JSON to *path*."""
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2)

    # ── public interface ──────────────────────────────────────────────────────

    def add_score(self, difficulty: str, score: int, word: str, player: str = "Player"):
        """
        Append a new score entry for *difficulty* and keep only the top-10.
        Saves immediately.
        """
        entry = {
            "player":     player,
            "score":      score,
            "word":       word,
            "timestamp":  time.strftime("%Y-%m-%d %H:%M"),
        }
        self.scores[difficulty].append(entry)
        # Keep leaderboard to top 10 sorted by score descending
        self.scores[difficulty].sort(key=lambda x: x["score"], reverse=True)
        self.scores[difficulty] = self.scores[difficulty][:10]
        self._save(SCORES_FILE, self.scores)

    def record_game(self, difficulty: str, won: bool, score: int):
        """Update aggregate statistics and save."""
        s = self.statistics
        s["total_games"]  += 1
        s["total_score"]  += score
        if won:
            s["total_wins"] += 1
            s[f"{difficulty}_wins"] += 1
        else:
            s["total_losses"] += 1
        if score > s["best_score"]:
            s["best_score"] = score
        self._save(STATISTICS_FILE, s)

    def get_high_score(self, difficulty: str) -> int:
        """Return the highest score ever recorded for *difficulty* (0 if none)."""
        board = self.scores.get(difficulty, [])
        return board[0]["score"] if board else 0

    def display_leaderboard(self, difficulty: str):
        """Pretty-print the top-10 leaderboard for one difficulty."""
        board = self.scores.get(difficulty, [])
        diff_color = {"easy": Fore.GREEN, "medium": Fore.YELLOW, "hard": Fore.RED}.get(difficulty, Fore.WHITE)
        print(f"\n{diff_color}🏆  {difficulty.upper()} LEADERBOARD{Style.RESET_ALL}")
        print_divider(color=diff_color)
        if not board:
            print(f"{Fore.WHITE}  No scores recorded yet.{Style.RESET_ALL}")
        else:
            for i, e in enumerate(board, 1):
                medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f" {i}."
                print(f"  {medal}  {Fore.WHITE}{e['player']:15}{Style.RESET_ALL}"
                      f"  {Fore.CYAN}{e['score']:>6} pts{Style.RESET_ALL}"
                      f"  {Fore.MAGENTA}({e['word']}){Style.RESET_ALL}"
                      f"  {Fore.WHITE}{e['timestamp']}{Style.RESET_ALL}")
        print_divider(color=diff_color)


# =============================================================================
# WORD GAME CORE
# =============================================================================

class WordGame:
    """
    Encapsulates one round of the word-guessing game.

    Attributes
    ----------
    difficulty : str          — "easy", "medium", or "hard"
    target     : str          — the word the player must guess
    word_data  : dict         — full dictionary entry for the word
    max_guesses: int          — starting guess budget
    guesses_left: int         — remaining guesses
    guessed_words: list[str]  — all attempts so far (in order)
    score_manager: ScoreManager
    current_score: int        — score accumulated this session
    """

    DIFFICULTY_CONFIG = {
        "easy":   {"guesses": 25, "hint_letters": 3, "base_score": 100},
        "medium": {"guesses": 15, "hint_letters": 1, "base_score": 200},
        "hard":   {"guesses": 10, "hint_letters": 1, "base_score": 300},
    }

    def __init__(self, difficulty: str, score_manager: ScoreManager):
        self.difficulty   = difficulty.lower()
        self.score_manager = score_manager
        cfg               = self.DIFFICULTY_CONFIG[self.difficulty]
        self.max_guesses  = cfg["guesses"]
        self.guesses_left = cfg["guesses"]
        self.base_score   = cfg["base_score"]
        self.hint_letters = cfg["hint_letters"]

        word_pool         = get_words_by_difficulty(self.difficulty)
        self.word_data    = random.choice(word_pool)
        self.target       = self.word_data["word"].lower()
        self.guessed_words: list[str] = []
        self.current_score = 0
        self._hint_mask   = self._build_hint_mask()

    # ── hint generation ───────────────────────────────────────────────────────

    def _build_hint_mask(self) -> list[str]:
        """
        Choose *hint_letters* random positions in the target word and reveal
        those characters; everything else becomes '_'.
        Returns a list the length of the target word.
        """
        mask      = ["_"] * len(self.target)
        positions = [i for i, c in enumerate(self.target) if c.isalpha()]
        revealed  = random.sample(positions, min(self.hint_letters, len(positions)))
        for pos in revealed:
            mask[pos] = self.target[pos].upper()
        return mask

    def generate_hint(self) -> str:
        """
        Return the current hint string, e.g.  "C _ M P _ T _ R".
        After each correct guess of a letter the mask is updated.
        """
        return " ".join(ch if ch != "_" else "_" for ch in self._hint_mask)

    def reveal_letter(self):
        """Reveal one additional random unrevealed letter (used as mercy after wrong guess)."""
        hidden = [i for i, ch in enumerate(self._hint_mask) if ch == "_" and self.target[i].isalpha()]
        if hidden:
            pos = random.choice(hidden)
            self._hint_mask[pos] = self.target[pos].upper()

    # ── similarity / scoring ──────────────────────────────────────────────────

    @staticmethod
    def levenshtein(s1: str, s2: str) -> int:
        """
        Classic edit-distance algorithm.
        Cost: O(|s1| × |s2|) time, O(|s2|) space.
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1, 1):
            curr = [i]
            for j, c2 in enumerate(s2, 1):
                cost = 0 if c1 == c2 else 1
                curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
            prev = curr
        return prev[-1]

    def calculate_similarity(self, guess: str) -> float:
        """
        Convert Levenshtein distance to a 0-100 similarity percentage.
        similarity = (1 - distance / max_len) * 100
        """
        dist    = self.levenshtein(guess.lower(), self.target)
        max_len = max(len(guess), len(self.target))
        return round((1 - dist / max_len) * 100, 1) if max_len else 0.0

    @staticmethod
    def get_feedback(similarity: float) -> str:
        """
        Map a similarity percentage to an emoji + label.
        """
        if similarity >= 90:
            return f"{Fore.RED}🔥 Extremely Close!{Style.RESET_ALL}"
        elif similarity >= 70:
            return f"{Fore.GREEN}🟢 Very Close{Style.RESET_ALL}"
        elif similarity >= 50:
            return f"{Fore.YELLOW}🟡 Getting There{Style.RESET_ALL}"
        elif similarity >= 30:
            return f"{Fore.MAGENTA}🟠 Far Away{Style.RESET_ALL}"
        else:
            return f"{Fore.RED}🔴 Very Far{Style.RESET_ALL}"

    def calculate_score(self, similarity: float, won: bool) -> int:
        """
        Score formula:
            base × (guesses_left / max_guesses)   — efficiency multiplier
            + guesses_left × 10                   — bonus per remaining guess
            + similarity bonus (0-50 pts)
        Only positive values are possible.
        """
        if not won:
            return 0
        efficiency     = (self.guesses_left / self.max_guesses)
        base_component = int(self.base_score * efficiency)
        guess_bonus    = self.guesses_left * 10
        sim_bonus      = int((similarity / 100) * 50)
        return max(0, base_component + guess_bonus + sim_bonus)

    # ── validation ────────────────────────────────────────────────────────────

    def is_valid_guess(self, guess: str) -> tuple[bool, str]:
        """
        Returns (is_valid, error_message).
        Checks:  non-empty, letters only, not already guessed.
        """
        if not guess:
            return False, "Please enter a word."
        if not all(c.isalpha() for c in guess):
            return False, "Your guess must contain only letters — no numbers or symbols."
        if guess.lower() in self.guessed_words:
            return False, f"You already guessed '{guess}'. Try something different."
        return True, ""

    # ── display helpers ───────────────────────────────────────────────────────

    def display_clue(self):
        """Show the appropriate clue for the current difficulty level."""
        diff_color = {"easy": Fore.GREEN, "medium": Fore.YELLOW, "hard": Fore.RED}[self.difficulty]

        print_divider(color=diff_color)
        if self.difficulty == "easy":
            print(f"{Fore.CYAN}📖  Meaning:{Style.RESET_ALL}")
            print(f"    {self.word_data['meaning']}")
        elif self.difficulty == "medium":
            print(f"{Fore.YELLOW}💡  Indirect Meaning:{Style.RESET_ALL}")
            print(f"    {self.word_data['indirect_meaning']}")
        else:
            print(f"{Fore.RED}🔮  Very Indirect Clue:{Style.RESET_ALL}")
            print(f"    {self.word_data['very_indirect_meaning']}")
        print_divider(color=diff_color)

    def display_hint_bar(self):
        """Show the hint letter mask prominently."""
        print(f"\n{Fore.MAGENTA}  Hint: {Style.RESET_ALL}{Fore.WHITE}{self.generate_hint()}{Style.RESET_ALL}")

    def display_guess_status(self):
        """Show remaining guesses as a visual progress bar."""
        ratio  = self.guesses_left / self.max_guesses
        filled = int(ratio * 20)
        bar    = "█" * filled + "░" * (20 - filled)
        color  = Fore.GREEN if ratio > 0.5 else (Fore.YELLOW if ratio > 0.25 else Fore.RED)
        print(f"\n{Fore.WHITE}  Guesses left: {color}{self.guesses_left}/{self.max_guesses}  [{bar}]{Style.RESET_ALL}")

    def display_guess_history(self):
        """Print all previous guesses."""
        if not self.guessed_words:
            return
        print(f"\n{Fore.CYAN}  Previous guesses:{Style.RESET_ALL} ", end="")
        for w in self.guessed_words:
            print(f"{Fore.WHITE}{w}{Style.RESET_ALL}", end="  ")
        print()

    # ── word-length helper ────────────────────────────────────────────────────

    def display_word_length(self):
        """Tell the player how many letters the target has."""
        print(f"\n{Fore.WHITE}  Word length: {Fore.CYAN}{len(self.target)} letters{Style.RESET_ALL}")


# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def display_statistics(score_manager: ScoreManager):
    """
    Full statistics screen showing aggregate data and per-difficulty leaderboards.
    """
    clear_screen()
    s = score_manager.statistics
    print(f"\n{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'  📊  GAME STATISTICS':^60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}\n")

    rows = [
        ("Total Games Played",  str(s["total_games"])),
        ("Total Wins",          f"{Fore.GREEN}{s['total_wins']}{Style.RESET_ALL}"),
        ("Total Losses",        f"{Fore.RED}{s['total_losses']}{Style.RESET_ALL}"),
        ("Win Rate",            f"{int(s['total_wins'] / s['total_games'] * 100) if s['total_games'] else 0}%"),
        ("Best Single Score",   f"{Fore.YELLOW}{s['best_score']}{Style.RESET_ALL}"),
        ("Total Score (all-time)", str(s["total_score"])),
        ("Easy Wins",           f"{Fore.GREEN}{s['easy_wins']}{Style.RESET_ALL}"),
        ("Medium Wins",         f"{Fore.YELLOW}{s['medium_wins']}{Style.RESET_ALL}"),
        ("Hard Wins",           f"{Fore.RED}{s['hard_wins']}{Style.RESET_ALL}"),
    ]
    for label, value in rows:
        print(f"  {Fore.WHITE}{label:<30}{Style.RESET_ALL}  {value}")

    print()
    for diff in ("easy", "medium", "hard"):
        score_manager.display_leaderboard(diff)

    print()
    input(f"{Fore.CYAN}  Press Enter to return to the main menu...{Style.RESET_ALL}")


# =============================================================================
# WIN / LOSS SCREENS
# =============================================================================

def show_win_screen(word: str, score: int, guesses_used: int):
    clear_screen()
    print(f"\n{Fore.GREEN}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║       🎉  CONGRATULATIONS!  🎉           ║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}")
    slow_print(f"  {Fore.YELLOW}You guessed it!  The word was: {Fore.WHITE}{word.upper()}{Style.RESET_ALL}", 0.03)
    print(f"\n  {Fore.CYAN}Guesses used:  {Fore.WHITE}{guesses_used}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}Score earned:  {Fore.YELLOW}{score} pts{Style.RESET_ALL}\n")


def show_loss_screen(word: str):
    clear_screen()
    print(f"\n{Fore.RED}")
    print("  ╔══════════════════════════════════════════╗")
    print("  ║          💀  GAME OVER  💀               ║")
    print("  ╚══════════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}")
    slow_print(f"  {Fore.YELLOW}The word was: {Fore.WHITE}{word.upper()}{Style.RESET_ALL}", 0.04)
    print()


# =============================================================================
# PLAY GAME
# =============================================================================

def play_game(difficulty: str, score_manager: ScoreManager) -> int:
    """
    Run one complete round.

    Returns the score earned (0 on a loss).
    """
    game = WordGame(difficulty, score_manager)
    diff_color = {"easy": Fore.GREEN, "medium": Fore.YELLOW, "hard": Fore.RED}[difficulty]

    loading_animation("Preparing your word", 1.2)
    clear_screen()

    # ── round header ──────────────────────────────────────────────────────────
    print(f"\n{diff_color}  ╔══════════════════════════════════════════╗")
    print(f"  ║  Difficulty: {difficulty.upper():<29}║")
    print(f"  ║  High Score: {score_manager.get_high_score(difficulty):<29}║")
    print(f"  ╚══════════════════════════════════════════╝{Style.RESET_ALL}\n")

    game.display_clue()
    game.display_word_length()
    game.display_hint_bar()
    game.display_guess_status()

    # ── main guess loop ───────────────────────────────────────────────────────
    while game.guesses_left > 0:
        game.display_guess_history()
        print()
        raw_guess = input(f"  {Fore.CYAN}Your guess: {Style.RESET_ALL}").strip()
        valid, error = game.is_valid_guess(raw_guess)

        if not valid:
            print(f"\n  {Fore.RED}⚠  {error}{Style.RESET_ALL}")
            time.sleep(1)
            continue

        guess = raw_guess.lower()
        game.guessed_words.append(guess)
        game.guesses_left -= 1

        similarity = game.calculate_similarity(guess)
        feedback   = game.get_feedback(similarity)

        # ── correct! ──────────────────────────────────────────────────────────
        if guess == game.target:
            score = game.calculate_score(100.0, won=True)
            game.current_score += score
            score_manager.add_score(difficulty, score, game.target)
            score_manager.record_game(difficulty, won=True, score=score)
            show_win_screen(game.target, score, game.max_guesses - game.guesses_left)
            return score

        # ── wrong guess — show analysis ────────────────────────────────────────
        clear_screen()
        game.display_clue()
        game.display_word_length()

        print(f"\n  {Fore.WHITE}Your guess:       {Fore.YELLOW}{guess}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Similarity score: {Fore.CYAN}{similarity}%{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}Feedback:         {feedback}")

        # Occasionally reveal an extra hint letter on bad guesses
        if similarity < 40 and random.random() < 0.35:
            game.reveal_letter()
            print(f"\n  {Fore.GREEN}💡 Bonus hint revealed!{Style.RESET_ALL}")

        game.display_hint_bar()
        game.display_guess_status()

    # ── out of guesses ────────────────────────────────────────────────────────
    score_manager.record_game(difficulty, won=False, score=0)
    show_loss_screen(game.target)
    return 0


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu():
    """
    Entry point. Shows the title screen and loops until the player exits.
    """
    score_manager = ScoreManager()

    while True:
        clear_screen()
        print(ASCII_TITLE)
        print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{'  WORD GUESSING GAME':^60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}\n")

        options = [
            ("1", Fore.GREEN,  "Easy   (25 guesses • full definition)"),
            ("2", Fore.YELLOW, "Medium (15 guesses • indirect clue)"),
            ("3", Fore.RED,    "Hard   (10 guesses • cryptic clue)"),
            ("4", Fore.CYAN,   "Statistics & Leaderboard"),
            ("5", Fore.WHITE,  "Exit"),
        ]
        for key, color, label in options:
            print(f"  {color}[{key}]{Style.RESET_ALL}  {Fore.WHITE}{label}{Style.RESET_ALL}")

        print()
        choice = input(f"  {Fore.CYAN}Choose an option: {Style.RESET_ALL}").strip()

        if choice == "1":
            _run_difficulty("easy", score_manager)
        elif choice == "2":
            _run_difficulty("medium", score_manager)
        elif choice == "3":
            _run_difficulty("hard", score_manager)
        elif choice == "4":
            display_statistics(score_manager)
        elif choice == "5":
            clear_screen()
            slow_print(f"\n  {Fore.YELLOW}Thanks for playing! Goodbye 👋{Style.RESET_ALL}", 0.04)
            print()
            break
        else:
            print(f"\n  {Fore.RED}Invalid choice. Please enter 1-5.{Style.RESET_ALL}")
            time.sleep(1)


def _run_difficulty(difficulty: str, score_manager: ScoreManager):
    """
    Play one or more rounds at a given difficulty level.
    Prompts the player to replay after each round.
    """
    while True:
        score = play_game(difficulty, score_manager)
        if score > 0:
            print(f"  {Fore.CYAN}Round score: {Fore.YELLOW}{score} pts{Style.RESET_ALL}")
        print()
        replay = input(f"  {Fore.CYAN}Play again at {difficulty.upper()}? [y/n]: {Style.RESET_ALL}").strip().lower()
        if replay not in ("y", "yes"):
            break


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        # Graceful Ctrl-C exit
        print(f"\n\n  {Fore.YELLOW}Game interrupted. Goodbye!{Style.RESET_ALL}\n")
        sys.exit(0)
