"""Queue orchestration and command-line parsing for aurora_code_loop."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Callable

from aurora_code_remote import Target, load_targets
from code_loop_files import slugify
from code_loop_state import load_state, save_state

log = logging.getLogger("code-loop")
SceneRunner = Callable[..., bool]


def run_queue(
    queue: list[dict],
    min_score: float,
    max_retries: int,
    scene_runner: SceneRunner,
    target: Target | None = None,
    use_tunnel: bool = False,
) -> int:
    state = load_state()
    succeeded = 0
    for index, entry in enumerate(queue, 1):
        scene_id = entry.get("name") or slugify(entry["prompt"])
        if scene_id in state["completed"]:
            log.info("[%s/%s] skip %s: already completed", index, len(queue), scene_id)
            succeeded += 1
            continue

        log.info("[%s/%s] === %s ===", index, len(queue), scene_id)
        entry_target = target
        if entry.get("target") and entry_target is None:
            entry_target = load_targets().get(entry["target"])
        ok = scene_runner(
            entry["prompt"],
            entry.get("name"),
            min_score,
            max_retries,
            state,
            target=entry_target,
            use_tunnel=use_tunnel,
        )
        if ok:
            state["completed"].append(scene_id)
            succeeded += 1
        elif scene_id not in state["failed"]:
            state["failed"].append(scene_id)
        save_state(state)

    log.info("=== queue done: %s/%s succeeded ===", succeeded, len(queue))
    return 0


def main(scene_runner: SceneRunner) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--prompt", type=str)
    parser.add_argument("--name", type=str)
    parser.add_argument("--min-score", type=float, default=0.65)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="remote target name from ~/.aurora_code_targets.json (deploy + validate over SSH)",
    )
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="Keep the server alive and expose it via localtunnel for manual UI testing",
    )
    args = parser.parse_args()

    target = None
    if args.target:
        targets = load_targets()
        target = targets.get(args.target)
        if target is None:
            log.error("unknown target %s. Available: %s", args.target, list(targets))
            return 2
        log.info("target locked: %s (%s)", args.target, target.remote())

    if args.prompt:
        queue = [{"prompt": args.prompt, "name": args.name}]
    elif args.queue:
        queue = json.loads(args.queue.read_text(encoding="utf-8"))
    else:
        log.error("provide --prompt or --queue")
        return 2
    return run_queue(
        queue,
        args.min_score,
        args.max_retries,
        scene_runner,
        target=target,
        use_tunnel=args.tunnel,
    )
