from __future__ import annotations
import json
import os
from collections import Counter
from dataclasses import dataclass, field
import sys
from typing import Mapping, Optional
import typer
from tabulate import tabulate

Candidate = str


@dataclass
class Round:
    scores: Mapping[Candidate, int]
    winner: Optional[Candidate]
    loser: Optional[Candidate]
    exhausted: int = 0
    defeat: Optional[Counter[Candidate]] = None
    ballots: list[Ballot] = field(default_factory=list)

    def __repr__(self):
        headers = ["Candidate", "Votes", "Percentage", "Result"]
        table = []
        for candidate, score in Counter(self.scores).most_common():
            if candidate == self.winner:
                win_loss_col = "Won"
            elif candidate == self.loser:
                win_loss_col = "Eliminated"
            else:
                win_loss_col = "-"
            table.append([candidate, score, score / len(self.ballots), win_loss_col])
        if self.exhausted > 0:
            table.append(
                ["EXHAUSTED", self.exhausted, self.exhausted / len(self.ballots), "-"]
            )
        out = [tabulate(table, headers, floatfmt=("", "", "%", ""))]
        if self.defeat:
            out.append(f"{self.loser} eliminated: {self.defeat}")
        return "\n".join(out)


@dataclass
class Result:
    winner: Candidate
    rounds: list[Round]
    ballots: list[Ballot]

    def __repr__(self) -> str:
        out = [f"{len(self.ballots)} ballots cast"]
        out.append(f"{len(self.ballots) // 2 + 1} votes to win")
        for i, round in enumerate(self.rounds):
            out.append(f"Round {i + 1}:")
            out.append(repr(round))
        out.append(f"Result: {self.winner} wins")
        return "\n".join(out)


@dataclass
class Ballot:
    ranking: list[Candidate]
    weight: int | float = 1

    @property
    def top_choice(self) -> Optional[Candidate]:
        try:
            return self.ranking[0]
        except IndexError:
            return None

    def prefers(self, first: Candidate, second: Candidate) -> bool:
        if first not in self.ranking or second not in self.ranking:
            return False
        if self.ranking.index(first) < self.ranking.index(second):
            return True

    def remove(self, cand: Candidate) -> None:
        try:
            self.ranking.remove(cand)
        except ValueError:
            pass


def _pairwise_loser(
    ballots: list[Ballot],
    first: Candidate,
    second: Candidate,
    outer_scores: Counter = None,
) -> tuple[Candidate, Counter[Candidate]]:
    scores = {first: 0, second: 0}
    for ballot in ballots:
        if ballot.prefers(first, second):
            scores[first] += 1
        if ballot.prefers(second, first):
            scores[second] += 1
    loser = min(scores, key=lambda x: scores[x])
    if outer_scores is not None:
        if scores[first] == scores[second]:
            loser = min(first, second, key=lambda x: outer_scores[x])
    return loser, scores


def btr_irv(ballots: list[Ballot]) -> Result:
    winner = None
    rounds: list[Round] = []
    threshold = len(ballots) // 2
    while winner is None:
        nexhausted = 0
        scores = Counter()
        for ballot in ballots:
            if ballot.top_choice is None:
                nexhausted += 1
                continue
            scores[ballot.top_choice] += 1
        if len(scores) == 1:
            winner, *_ = scores
            rounds.append(
                Round(scores, winner, loser=None, exhausted=nexhausted, ballots=ballots)
            )
            continue
        top_scoring_candidate = max(scores, key=lambda x: scores[x])
        if scores[top_scoring_candidate] > threshold:
            winner = top_scoring_candidate
            rounds.append(
                Round(
                    scores,
                    winner=winner,
                    loser=None,
                    nexhausted=nexhausted,
                    ballots=ballots,
                )
            )
            continue
        # Eliminate the least-preferred of the bottom two candidates
        *_, (bot2, _), (bot1, _) = scores.most_common()
        (loser, loser_score) = _pairwise_loser(ballots, bot2, bot1, outer_scores=scores)
        for ballot in ballots:
            ballot.remove(loser)
        rounds.append(
            Round(scores, winner=None, loser=loser, defeat=loser_score, ballots=ballots)
        )
    return Result(winner, rounds, ballots)


def irv(ballots: list[Ballot]) -> Result:
    winner = None
    rounds: list[Round] = []
    threshold = len(ballots) // 2
    while winner is None:
        exhausted = 0
        scores = Counter()
        for ballot in ballots:
            if ballot.top_choice is None:
                exhausted += 1
                continue
            scores[ballot.top_choice] += 1
        if len(scores) == 1:
            winner, *_ = scores
            rounds.append(
                Round(scores, winner, loser=None, exhausted=exhausted, ballots=ballots)
            )
            continue
        top_scoring_candidate = max(scores, key=lambda x: scores[x])
        if scores[top_scoring_candidate] > threshold:
            winner = top_scoring_candidate
            rounds.append(
                Round(
                    scores,
                    winner=winner,
                    loser=None,
                    nexhausted=exhausted,
                    ballots=ballots,
                )
            )
            continue
        # Eliminate the candidate with the least first choices
        loser = min(scores, key=lambda x: scores[x])
        for ballot in ballots:
            ballot.remove(loser)
        rounds.append(Round(scores, winner=None, loser=loser, ballots=ballots))
    return Result(winner, rounds, ballots)


@dataclass
class STVResult:
    winners: list[Candidate]
    rounds: list[Round]
    ballots: list[Ballot]

    def __repr__(self) -> str:
        out = [f"{len(self.ballots)} ballots cast"]
        out.append(
            f"{len(self.ballots) // (len(self.winners) + 1) + 1} votes to win a seat"
        )
        for i, round in enumerate(self.rounds):
            out.append(f"Round {i + 1}:")
            out.append(repr(round))
        for i, winner in enumerate(self.winners):
            out.append(f"Seat {i + 1}: {winner} wins")
        return "\n".join(out)


def stv(ballots: list[Ballot], seats: int = 1) -> STVResult:
    winners = []
    rounds = []
    threshold = len(ballots) // (seats + 1)
    eliminated = []
    while len(winners) < seats:
        scores = Counter()
        exhausted = 0
        for ballot in ballots:
            if ballot.top_choice is None:
                exhausted += 1
                continue
            scores[ballot.top_choice] += ballot.weight
        if len(scores) == 1:
            winner, *_ = scores
            winners.append(winner)
            rounds.append(
                Round(
                    scores,
                    winner=winner,
                    loser=None,
                    exhausted=exhausted,
                    ballots=ballots,
                )
            )
            for ballot in ballots:
                ballot.remove(winner)
            continue
        # if not scores:
        #     while len(winners) < seats:
        #         winners.append(eliminated.pop())
        #     continue
        threshold = (len(ballots) - exhausted) // (seats + 1)
        top_scorer = max(scores, key=lambda x: scores[x])
        if scores[top_scorer] > threshold:
            winners.append(top_scorer)
            rounds.append(
                Round(
                    scores,
                    winner=top_scorer,
                    loser=None,
                    ballots=ballots,
                    exhausted=exhausted,
                )
            )
            surplus = scores[top_scorer] - threshold
            for ballot in ballots:
                if ballot.top_choice == top_scorer:
                    ballot.weight *= surplus / scores[top_scorer]
                ballot.remove(top_scorer)
        else:
            # *_, (second_from_bottom, _), (bottom, _) = scores.most_common()
            # (eliminandum, defeat) = _pairwise_loser(ballots, second_from_bottom, bottom, outer_scores=scores)
            defeat = None
            eliminandum = min(scores, key=lambda x: scores[x])
            for ballot in ballots:
                ballot.remove(eliminandum)
            rounds.append(
                Round(
                    scores,
                    winner=None,
                    loser=eliminandum,
                    defeat=defeat,
                    ballots=ballots,
                    exhausted=exhausted,
                )
            )
            eliminated.append(eliminandum)
    return STVResult(winners, rounds, ballots)


@dataclass
class PRResult:
    party_votes: dict[str, int]
    party_seats: dict[str]

    def __repr__(self) -> str:
        headers = ["Party", "Votes", "Percentage", "Seats", "Seat %"]
        table = []
        for party in sorted(
            self.party_votes, key=lambda x: self.party_votes[x], reverse=True
        ):
            seats = self.party_seats[party]
            vote_percentage = (
                f"{self.party_votes[party] / sum(self.party_votes.values()):%}"
            )
            seat_percentage = (
                f"{self.party_seats[party] / sum(self.party_seats.values()):%}"
            )
            table.append(
                [
                    party,
                    self.party_votes[party],
                    vote_percentage,
                    seats,
                    seat_percentage,
                ]
            )

        return tabulate(table, headers)


def webster_pr(party_votes: dict[Candidate, int], seats: int) -> PRResult:
    party_seats = Counter()

    while sum(party_seats.values()) < seats:
        quotients = {}
        for party, votes in party_votes.items():
            quotients[party] = votes / (2 * party_seats[party] + 1)

        winner = max(quotients, key=lambda x: quotients[x])
        party_seats[winner] += 1

    return PRResult(party_votes, party_seats)


def get_ballots_from_file(ballot_file: os.PathLike) -> list[Ballot]:
    with open(ballot_file) as fp:
        data = json.load(fp)
    result: list[Ballot] = []
    for datum in data:
        ranking: list[Candidate] = datum["ranking"]
        count: int = datum.get("count", 0)
        for _ in range(count):
            result.append(Ballot(ranking.copy()))
    return result


def main(
    ballot_file: str,
    method: str = typer.Option("default", "--method", "-m"),
    seats: int = 1,
):
    try:
        ballots = get_ballots_from_file(ballot_file)
    except:
        with open(ballot_file) as fp:
            ballots = json.load(fp)
    match method:
        case "btr" | "btr-irv" | "b2":
            result = btr_irv(ballots)
        case "irv":
            result = irv(ballots)
        case "stv":
            result = stv(ballots, seats)
        case "webster" | "pr":
            result = webster_pr(ballots, seats)
        case _:
            if seats > 1:
                result = stv(ballots, seats)
            else:
                result = btr_irv(ballots)

    print(result)


if __name__ == "__main__":
    typer.run(main)
