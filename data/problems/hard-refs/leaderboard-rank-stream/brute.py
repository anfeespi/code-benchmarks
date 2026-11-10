def leaderboard_ranks(submissions):
    best, best_time, out = {}, {}, []
    for i, (player, score) in enumerate(submissions):
        if player not in best or score > best[player]:
            best[player] = score
            best_time[player] = i
        ranking = sorted(best, key=lambda p: (-best[p], best_time[p]))
        out.append(ranking.index(player) + 1)
    return out
