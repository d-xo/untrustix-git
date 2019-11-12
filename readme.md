# untrustix-git

This is a design for a git backed, cryptographically verifiable, append only log of nix build
results for use within some binary transparency scheme. It makes use of the new [partial
clone](https://git-scm.com/docs/partial-clone) features in git to allow for very lightweight
log followers (hundreds of kilobytes of local state required).

As far as I can tell there are no major git hosting services that currently support partial clones
in git, although gitlab are currently working to enable support
([ref](https://docs.gitlab.com/ee/topics/git/partial_clone.html)). It does however work with self
hosted repos (I have tested with the `ssh` and `git` protocols).

## Repo Layout

Results are stored in a hash tree in the repo root, keyed by their store hash, and sharded into
subdirectories (e.g. the expected contents of the store path identified by
`zzlfqv4p4hf55saim00zc9vvqj08nxjb` would be written to a file at
`zz/lf/qv4p4hf55saim00zc9vvqj08nxjb`). The sharding keeps directory (and tree object) sizes sane and
allows for the construction of compact proofs of:

- `inclusion`: a given build result is included in a given hash tree
- `consistency`: a given hash tree is append only relative to an older version

More thought is required to select an optimum tree depth. There is probably a trade off between
the sizes of the inclusion and consistency proofs here.

An example repo can be found here: https://github.com/xwvvvvwx/untrustix-git-testdata.

## Proofs

### Inclusion

The inclusion proof is the familiar merkle branch proof. Given a leaf node and the branch from the
root to the leaf, the verifier can combine the leaf with the provided intermediate hashes and
confirm that they produce the expected root hash. This assumes that the client has obtained
knowledge of the root hash through some trusted side channel.

### Consistency

This proof assumes that only a single new leaf has been added to the tree. The verifier knows the
root hash of the old tree and the new tree. The prover provides:

1. A full branch in the old tree to the leaf where the new content will be inserted
1. The new content and it's path in the tree

The verifier does the following:

1. Verifies that the branch in the old tree is valid
1. Recomputes the branch with the new content added, reusing any unchanged intermediate hashes from
   the old branch, and verifies that it produces the new root hash

This works because the branch in the old tree is a commitment to the state of the entire tree. If we
reuse the unchanged hashes from the old branch while computing the new root hash, then we can be
sure that the only change to the tree was the addition of the new content.

If each new build result is added as a new commit, then the consistency proof can be written to the
commit message, meaning log followers need only retain a single commit object locally.

## Builders

Builders need to store the latest commit and associated tree objects only. They can drop old commits
and all blobs. For each new build result, builders:

1. Insert the build result
1. Construct the consistency proof
1. Commit the new state and write the consistency proof as the commit message

## Clients

Log followers are lightweight and need store only the most recent commit object (trees / blobs are
not required) for logs they are interested in. The number of operations required to lookup a build
result, as well as the amount of local state required is constant as the number of build results
increases.

### Synchronisation

Clients start from a known good commit, and pull newer commits in order from the oldest to the
newest. As they receive new commits, they verify the consistency proofs. Once a newer commit has
been verified, all older commits can be discarded. This operation scales linearly in time with the
number of commits.

### Lookup

Starting from the root, clients move down the tree to the desired leaf, fetching intermediate tree
objects as needed (using `git fetch-pack --filter=tree:0 <REPO> <OBJECT_HASH>`). Once they have
fetched the full branch, they combine all hashes to verify the inclusion proof.

## Testing

A small script `builder.py` is included in this repo that can be used to generate fake build results
and commit them to a log.  It currently does not write the full consistency proof to the commit
message, only the store hash and content that was added.

I ran it for a few days and generated a test repository with ~3.3 million builds. This repo is
7.6GiB on disk, and is available here: https://github.com/xwvvvvwx/untrustix-git-testdata.

You can emulate a client by fetching using `git clone --filter=tree:0 --depth=1 --no-checkout
--no-hardlinks file://<PATH_TO_REPO> client`. This will fetch only the latest commit object. It will
not fetch any tree or blob objects referenced in the commit. It will not checkout any data into the
worktree. Note that this must be done on a local copy of the repo, as github currently does not
support partial clones.

You can then query individual build results by recursively calling `git fetch-pack --filter=tree:0
file://<PATH_TO_REPO> <OBJECT_HASH>` inside the client repository until you reach a leaf.
