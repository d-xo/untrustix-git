#! /usr/bin/env python3

from argparse import ArgumentParser
from pathlib import Path
from tempfile import mkdtemp
from typing import Optional
import re
import subprocess

import common

def run(cmd: str, cwd: Optional[Path] = None) -> str:
    """run `cmd` and return the output, print stderr and bail if it fails"""
    try:
        return str(
            subprocess.run(
                cmd.split(), capture_output=True, check=True, cwd=cwd
            ).stdout.decode("utf-8")
        )
    except subprocess.CalledProcessError as e:
        print(e.stderr.decode("utf-8"))
        exit(1)


def fetch_object(remote: str, repo: str, oid: str) -> None:
    """fetch the object identified by `oid` into `repo` from `remote`"""
    run(f"git fetch-pack --filter=tree:0 {remote} {oid}", cwd=repo)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Fetch a build result from an untrustix-git repo using the lightweight protocol"
    )
    parser.add_argument(
        "--remote",
        type=str,
        required=True,
        help="The repo containing the build log, can be any repo url supported by git",
    )
    parser.add_argument(
        "store_hash",
        type=str,
        help="The store hash identifying the build that should be fetched",
    )
    args = parser.parse_args()

    repo = mkdtemp()

    run(f"git clone --filter=tree:0 --depth=1 --bare --no-hardlinks {args.remote} {repo}")
    commit_id = run("git rev-parse HEAD", cwd=repo).strip("\n")
    repo_size=run(f"du -sh {repo}").split()[0]
    print()
    print(f"initialized light client for {args.remote} in {repo}")
    print(f"current commit: {commit_id}")
    print(f"repo size: {repo_size}")
    print()

    # --- tree root ---

    raw_commit = run(f"git cat-file -p {commit_id}", cwd=repo)
    tree_root = re.search(r"^tree\s(\w{40})$", raw_commit, re.MULTILINE).groups()[0]
    print(f"fetching tree root: {tree_root}")
    fetch_object(args.remote, repo, tree_root)

    shards = common.shards(args.store_hash)

    # --- branch ---

    raw_tree = run(f"git cat-file -p {tree_root}", cwd=repo)
    subtree = re.search(r"^040000\stree\s(\w{40})\s" + shards[0] + "$", raw_tree, re.MULTILINE).groups()[0]
    print(f"fetching subtree for {shards[0]}: {subtree}")
    fetch_object(args.remote, repo, subtree)

    raw_tree = run(f"git cat-file -p {subtree}", cwd=repo)
    subtree = re.search(r"^040000\stree\s(\w{40})\s" + shards[1] + "$", raw_tree, re.MULTILINE).groups()[0]
    print(f"fetching subtree for {shards[1]}: {subtree}")
    fetch_object(args.remote, repo, subtree)

    raw_tree = run(f"git cat-file -p {subtree}", cwd=repo)
    blob = re.search(r"^100644\sblob\s(\w{40})\s" + shards[2] + "$", raw_tree, re.MULTILINE).groups()[0]
    print(f"fetching blob for {shards[2]}: {blob}")
    fetch_object(args.remote, repo, blob)

    # --- output result ---

    content = run(f"git cat-file -p {blob}", cwd=repo)
    repo_size=run(f"du -sh {repo}").split()[0]
    print()
    print(f"expected nar hash for {args.store_hash} is: {content}")
    print(f"repo size: {repo_size}")
