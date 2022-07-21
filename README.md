# rcvplus
rcvplus -- Python script for methods related to Instant Runoff Voting and Proportional Representation.

rcplus.py can do single-seat elections (with either traditional IRV or BTR-IRV), multi-seat elections (with STV),
or Webster/Sainte-Laguë party-list proportional representation.

Some example JSON files are given in the `examples/` directory.

Essentially:

1. For ranked-choice voting methods, pass a list of JSON objects. Each object may have an optional `count` member,
which corresponds to the number of ballots having a particular ordering in a given election. It must have a `ranking`
member, which ranks choices of candidate (first choice is array element 0, etc.).
2. For proportional representation, simply pass a JSON object which maps party names to votes received.
