def leaderboard_ranks(submissions):
    # correct but O(n * players): counts players ahead by scanning the whole board
    best, best_time, out = {}, {}, []
    for i, (player, score) in enumerate(submissions):
        if player not in best or score > best[player]:
            best[player] = score
            best_time[player] = i
        b, t = best[player], best_time[player]
        ahead = sum(1 for q in best if best[q] > b or (best[q] == b and best_time[q] < t))
        out.append(ahead + 1)
    return out
