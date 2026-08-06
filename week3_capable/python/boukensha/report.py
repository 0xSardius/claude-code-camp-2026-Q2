"""Session summary reporter (week2 observability M5).

Reads one or more JSONL session logs and answers the questions you actually
have about an unattended run: what did it spend, how hard is it working per
turn, is the cache doing anything, which tools are failing, and did anything
truncate or stall.

    uv run python -m boukensha.report                 # every session in .boukensha/sessions
    uv run python -m boukensha.report <file.jsonl>    # one session
    uv run python -m boukensha.report --json          # machine-readable

Deliberately standalone -- NOT coupled to the TUI. The TUI is for watching one
live session; this is for reading finished ones and for producing the
before/after numbers the token pillar is measured on.

Reads both log formats. Week1 logs carry a full `messages` array per prompt
event and no `cost`; week2 logs carry a `digest` and cost fields. Neither shape
is assumed -- missing fields are reported as unknown rather than zero, because
"free" and "unmeasured" are different facts and rendering the second as the
first quietly under-reports.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from ._module_state import config as boukensha_config


def _fmt_int(n):
    return f"{n:,}" if isinstance(n, int) else "?"


def _fmt_usd(v):
    return f"${v:,.4f}" if isinstance(v, (int, float)) else "unknown"


class SessionReport:
    """Aggregate of one or more session logs."""

    def __init__(self, events, *, sources=()):
        self.events = events
        self.sources = list(sources)

    @classmethod
    def from_paths(cls, paths):
        events, sources, per_source = [], [], []
        for p in paths:
            path = Path(p)
            if not path.is_file():
                continue
            sources.append(path)
            own = []
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    own.append(json.loads(line))
                except json.JSONDecodeError:
                    # A run killed mid-write leaves a torn final line. Skip it
                    # rather than refusing to report on the whole session --
                    # the interrupted runs are often the ones worth reading.
                    continue
            events.extend(own)
            per_source.append(own)
        report = cls(events, sources=sources)
        report._per_source = per_source
        return report

    def _turn_count(self):
        """Turns, counted PER SESSION with the turn_end fallback applied per
        session rather than across the whole aggregate.

        `logger.turn()` is emitted only by Repl.run_turn, while `turn_end`
        comes from Agent itself -- so a session driven through Agent.run()
        directly (every example script, and both bakery runs) logs turn_end and
        no turn. Applying the fallback to the aggregate meant that as soon as
        ONE source contained a `turn` event, every turn-less session
        contributed its iterations and costs to the numerators of
        cost_per_turn and iterations_per_turn while contributing nothing to the
        denominator. Both metrics came out silently inflated. Found by code
        review.
        """
        sources = getattr(self, "_per_source", None) or [self.events]
        total = 0
        for evs in sources:
            turns = sum(1 for e in evs if e.get("phase") == "turn")
            total += turns or sum(1 for e in evs if e.get("phase") == "turn_end")
        return total

    @classmethod
    def from_default_dir(cls):
        d = Path(boukensha_config().dir) / "sessions"
        return cls.from_paths(sorted(d.glob("*.jsonl")))

    def _by_phase(self, phase):
        return [e for e in self.events if e.get("phase") == phase]

    def summary(self):
        responses = self._by_phase("response")
        tool_results = self._by_phase("tool_result")

        tokens = Counter()
        for e in responses:
            u = e.get("usage")
            if not isinstance(u, dict):
                continue
            for key in ("input_tokens", "output_tokens",
                        "cache_read_input_tokens", "cache_creation_input_tokens"):
                v = u.get(key)
                if isinstance(v, int):
                    tokens[key] += v

        # 06_the_logger..11_tui wrote the cost under `cost_usd`; 12_context
        # dropped it; week2 restored it as `cost`. Reading only one key made
        # the reporter call genuinely-recorded week1 spend "unknown". Found by
        # code review.
        costs = []
        for e in responses:
            for key in ("cost", "cost_usd"):
                v = e.get(key)
                if isinstance(v, (int, float)):
                    costs.append(v)
                    break
        turns = self._by_phase("turn")
        iterations = self._by_phase("iteration")
        turn_ends = Counter(e.get("reason") for e in self._by_phase("turn_end"))

        # Cache hit rate is against everything the model READ, not just what we
        # paid full price for -- input_tokens is the uncached remainder only.
        read = tokens["cache_read_input_tokens"]
        total_in = tokens["input_tokens"] + read + tokens["cache_creation_input_tokens"]

        n_turns = self._turn_count()
        return {
            "sessions": len(self.sources),
            "events": len(self.events),
            "turns": n_turns,
            "iterations": len(iterations),
            "iterations_per_turn": (len(iterations) / n_turns) if n_turns else None,
            "tokens": dict(tokens),
            "total_input_read": total_in,
            "cache_hit_rate": (read / total_in) if total_in else None,
            "cost_total": sum(costs) if costs else None,
            "cost_per_turn": (sum(costs) / n_turns) if costs and n_turns else None,
            "priced_responses": f"{len(costs)}/{len(responses)}",
            "turn_end_reasons": dict(turn_ends),
            "tool_calls": Counter(e.get("name") for e in self._by_phase("tool_call")),
            "tool_failures": Counter(
                e.get("name") for e in tool_results if e.get("ok") is False
            ),
            "truncations": len(self._by_phase("truncated")),
            "compactions": len(self._by_phase("compaction")),
            "hook_errors": Counter(e.get("hook") for e in self._by_phase("hook_error")),
            "failed_turns": Counter(
                str(e.get("error", "")).split(":")[0] for e in self._by_phase("turn_failed")
            ),
            "reasoning_events": len(self._by_phase("reasoning")),
            "log_bytes": sum(p.stat().st_size for p in self.sources),
            **self._capability(sum(costs) if costs else None),
        }

    def _capability(self, cost_total):
        """The three numbers docs/plans/week3/README.md grades the week on.

        They were specified as "computable from the week 2 session reporter"
        and were not: nothing here read the driver's lines, so every figure was
        being worked out by hand from raw JSONL after each run. A number that
        only exists when someone remembers to calculate it is not a metric.

        Everything below comes from structured fields. Nothing matches on the
        text of a tool result -- those strings are ours and would probably be
        stable, but a reporter that reads its own prose is one rewording away
        from silently reporting zero.
        """
        cycles = self._by_phase("driver_cycle")
        runs = self._by_phase("driver_run")

        mech = sum(c.get("mechanical_actions", 0) or 0 for c in cycles)
        model = sum(c.get("model_actions", 0) or 0 for c in cycles)
        actions = mech + model

        # Progress is experience across a whole run; a per-cycle delta would
        # miss the kills that land on a later tick.
        gained = 0
        for r in runs:
            a, b = r.get("starting_exp"), r.get("ending_exp")
            if isinstance(a, int) and isinstance(b, int) and b > a:
                gained += b - a

        # A recovery EPISODE is one sit-down. The follow-on cycles that wait
        # are noted "cycle N", so counting every resting cycle would score a
        # single long rest as a dozen separate incidents.
        episodes = sum(1 for c in cycles
                       if c.get("action") == "resting"
                       and not re.match(r"^cycle \d+$", str(c.get("note", ""))))
        completed = sum(1 for c in cycles if c.get("action") == "stood_up")
        endings = Counter(r.get("stopped_because") for r in runs)
        bad = endings.get("stalled", 0) + endings.get("stuck_recovering", 0)

        return {
            "driver_cycles": len(cycles),
            "driver_runs": len(runs),
            "mechanical_actions": mech,
            "model_actions": model,
            "judgment_ratio": (model / actions) if actions else None,
            "experience_gained": gained,
            "cost_per_experience": (cost_total / gained) if cost_total and gained else None,
            "recovery_episodes": episodes,
            "recoveries_completed": completed,
            "run_endings": dict(endings),
            "runs_ended_badly": bad,
        }

    def render(self):
        s = self.summary()
        out = []
        add = out.append

        add(f"sessions   {s['sessions']}   ({_fmt_int(s['log_bytes'])} bytes of log, {_fmt_int(s['events'])} events)")
        add("")
        add("WORK")
        add(f"  turns                {_fmt_int(s['turns'])}")
        add(f"  iterations           {_fmt_int(s['iterations'])}"
            + (f"   ({s['iterations_per_turn']:.1f} per turn)" if s["iterations_per_turn"] else ""))
        for reason, n in sorted(s["turn_end_reasons"].items(), key=lambda kv: -kv[1]):
            add(f"    ended {str(reason):<14} {n}")
        add("")
        add("SPEND")
        t = s["tokens"]
        add(f"  input (billed)       {_fmt_int(t.get('input_tokens', 0))}")
        add(f"  output               {_fmt_int(t.get('output_tokens', 0))}")
        add(f"  cache read           {_fmt_int(t.get('cache_read_input_tokens', 0))}")
        add(f"  cache write          {_fmt_int(t.get('cache_creation_input_tokens', 0))}")
        rate = s["cache_hit_rate"]
        add(f"  cache hit rate       {f'{rate:.1%}' if rate is not None else 'n/a'}"
            + ("   <- caching is not on" if rate == 0 and not t.get("cache_creation_input_tokens") else ""))
        add(f"  cost                 {_fmt_usd(s['cost_total'])}   (priced: {s['priced_responses']} responses)")
        if s["cost_per_turn"]:
            add(f"  cost per turn        {_fmt_usd(s['cost_per_turn'])}")
        if s["driver_cycles"]:
            add("")
            add("CAPABILITY   (docs/plans/week3/README.md)")
            ratio = s["judgment_ratio"]
            add(f"  driver runs          {s['driver_runs']}   ({_fmt_int(s['driver_cycles'])} cycles)")
            add(f"  judgment ratio       {f'{ratio:.0%}' if ratio is not None else 'n/a'}"
                f"   of actions needed the model"
                f"   ({_fmt_int(s['model_actions'])} model, "
                f"{_fmt_int(s['mechanical_actions'])} mechanical)")
            per = s["cost_per_experience"]
            add(f"  experience gained    {_fmt_int(s['experience_gained'])}")
            add(f"  cost per experience  {_fmt_usd(per) if per else 'n/a'}"
                + ("   <- spend per unit of progress, not per turn" if per else ""))
            add(f"  recovery             {s['recoveries_completed']}/{s['recovery_episodes']} "
                f"episodes recovered from")
            if s["run_endings"]:
                for reason, n in sorted(s["run_endings"].items(), key=lambda kv: -kv[1]):
                    flag = "   <-- never got to work" if reason == "stuck_recovering" else ""
                    add(f"    ended {str(reason):<16} {n}{flag}")
        add("")
        add("HEALTH")
        add(f"  truncated responses  {s['truncations']}")
        add(f"  compactions          {s['compactions']}")
        add(f"  reasoning events     {s['reasoning_events']}")
        failures = sum(s["tool_failures"].values())
        add(f"  tool failures        {failures}"
            + (f"   ({', '.join(f'{k}x{v}' for k, v in s['tool_failures'].most_common(3))})" if failures else ""))
        if s["hook_errors"]:
            add(f"  hook errors          {sum(s['hook_errors'].values())}   ({dict(s['hook_errors'])})")
        failed = sum(s["failed_turns"].values())
        if failed:
            add(f"  failed turns         {failed}   ({', '.join(f'{k}x{v}' for k, v in s['failed_turns'].most_common(3))})"
                "   <-- turns that raised instead of finishing")
        add("")
        add("TOOLS")
        if not s["tool_calls"]:
            add("  (none)")
        for name, n in s["tool_calls"].most_common(12):
            add(f"  {str(name):<20} {n}")
        return "\n".join(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    report = SessionReport.from_paths(argv) if argv else SessionReport.from_default_dir()
    if not report.sources:
        print("no session logs found", file=sys.stderr)
        return 1

    if as_json:
        s = report.summary()
        # Counters and Paths aren't JSON-serializable as-is.
        s["tool_calls"] = dict(s["tool_calls"])
        s["tool_failures"] = dict(s["tool_failures"])
        s["hook_errors"] = dict(s["hook_errors"])
        print(json.dumps(s, indent=2))
    else:
        print(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
