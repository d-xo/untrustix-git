# untrustix-git

This is a design / proof of concept for a git backed, untrusted, append only log of nix build
results for use within some build transparency scheme. It makes use of the new [partial
clone](https://git-scm.com/docs/partial-clone) features in git to allow for very lightweight log
followers (hundreds of kilobytes of local state required).

Using git to implement the log is nice because:

- Git is simple, robust, and well understood by the majority of the worlds software developers
- The log is stored in a well documented and widely understood format, and can be easily inspected
  using existing tooling (e.g. manual lookups in the github webui are possible)
- Hosting logs is extremely simple (for small logs it should even be possible to use github)

## Repo Layout

Results are stored in a hash tree in the repo root, keyed by their store hash, and sharded into
subdirectories (e.g. the expected contents of the store path identified by
`zzlfqv4p4hf55saim00zc9vvqj08nxjb` would be written to a file at
`zz/lf/qv4p4hf55saim00zc9vvqj08nxjb`). The sharding keeps directory (and tree object) sizes sane and
allows for the construction of compact (hundreds of kilobytes) proofs of:

- `inclusion`: a given build result is included in a given hash tree
- `consistency`: a given hash tree is append only relative to an older version

More thought is required to select an optimum tree depth.

The repository need never be checked out into a worktree, meaning that it can be stored on disk
using the highly compressed packfile format. All operations can work on the packfiles directly. This
means that the disk space requirements for the full log are not as onerous as one would expect (e.g. my
test repo with ~3.3 million builds needs 7.6G on disk).

An example repo can be found here: https://github.com/xwvvvvwx/untrustix-git-testdata.

## Proofs

### Inclusion

The inclusion proof is the familiar merkle branch proof. Given a leaf node and the branch from the
root to the leaf, the verifier can combine the leaf with the provided intermediate hashes and
confirm that they produce the expected root hash. This assumes that the verifier has obtained
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

## Clients

### Builders

Builders realise derivations and write build results to the log.

Builders need to store the latest commit and associated tree objects only, they can drop old commits
and all blobs. Even for extremely large logs (hundreds of millions of entries), this should only
requires tens of gigabytes of disk space.

For each new build result, builders:

1. Insert the build result
1. Construct the consistency proof
1. Commit the new state and write the consistency proof as the commit message

### Followers

Followers query build results from logs. Log followers are lightweight and need store only the most
recent commit object (trees / blobs are not required). This means they need only store a few hundred
kilobytes of data for each log they are interested in.

#### Log Synchronisation

Followers start from a known good commit, and pull newer commits in order from the oldest to the
newest. As they receive new commits, they verify the consistency proofs. Once a newer commit has
been verified, all older commits can be discarded. This operation scales linearly in time with the
number of commits.

#### Build Lookup

Starting from the root, followers move down the tree to the desired leaf, fetching intermediate tree
objects as needed (using `git fetch-pack --filter=tree:0 <REPO> <OBJECT_HASH>`). Once they have
fetched the full branch, they combine all hashes to verify the inclusion proof. The number of
network requests required to lookup a build result remains constant as the number of builds
increases.

## Malicious Logs

Most forms of bad behaviour can be observed by clients, and log operators cannot do any of the
following without being detected:

- Remove log entries
- Modify existing log entries
- Lie about the presence of a build in the log

The protocol as described in this document does however allow log operators to fork the log and
present different versions of the log to different followers. This would allow targeted attacks
against individual users. To counter this the protocol should be extended to provide some venue
where log followers can gossip commit hashes of logs that they follow.

## Testing

A small script `builder.py` is included in this repo that can be used to generate fake build results
and commit them to a log.  It currently does not write the full consistency proof to the commit
message, only the store hash and content that was added.

I ran it for a few days and generated a test repository with ~3.3 million builds. This repo is
7.6GB on disk, and is available here: https://github.com/xwvvvvwx/untrustix-git-testdata.

You can emulate a lightweight follower by fetching using `git clone --filter=tree:0 --depth=1
--no-checkout --no-hardlinks file://<PATH_TO_REPO> client`. This will fetch only the latest commit
object. It will not fetch any tree or blob objects referenced in the commit. It will not checkout
any data into the worktree. Note that this must be done on a local copy of the repo, as github
currently does not support partial clones.

You can then query individual build results by recursively calling `git fetch-pack --filter=tree:0
file://<PATH_TO_REPO> <OBJECT_HASH>` inside the client repository until you reach the desired leaf
node.

## Practicality

### Partial Clone Support

There are unfortunately no major git hosting services that currently support partial clone, although
gitlab are currently testing an alpha implementation behind a feature flag
([ref](https://docs.gitlab.com/ee/topics/git/partial_clone.html)). It does however work with self
hosted repos (I have tested with the `ssh` and `git` protocols).

The lightweight log follower protocol outlined in this document could be implemented using the
github [git data api](https://developer.github.com/v3/git/), but the rate limit (5000 requests per
hour for authenticated users) would probably become restrictive fairly quickly.

Even without support for partial clone, it may be reasonable to host small logs (< 100,000 builds)
on github. In this scenario, followers would perform shallow clones instead of partial clones,
bringing their local state requirements up to 10s of megabytes per log.

### Scalability

The resource requirements imposed on builders and log followers seem reasonable, and should scale
fairly well even with very large logs. Potential scalability issues would rather seem to be a
concern for the log operators.

Hydra has performed ~100,000,000 builds over the last 10 years, and is currently producing ~1,200,000
builds per month. We should assume that this number will increase. It does not seems unreasonable to
expect the largest logs to reach at least 500,000,000 entries in the next decade.

My 3.3 million build test repo takes up 7.6GB on disk, extrapolating out to a 500,000,000 entry log,
we can expect the repo to require ~1TB of disk usage.

Operations on the full log are slow and expensive. Running `git gc` on my (relatively small) test
repo already takes ~15 minutes on a modern quad core i7 laptop. Performing whole repo operations on
very large logs may become tedious or problematic.

Very popular logs (e.g. hydra) will be queried on every build by most (all?) NixOS users. It is
currently unclear what kind of load this would place on log operators. It should be noted that if
log followers are lightweight, each query will be composed of multiple network requests as clients
recursively walk down the tree to the leaf. It should be possible to apply some client side caching
logic to reduce the expense here.

