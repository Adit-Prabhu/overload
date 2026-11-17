"""The knowledge boundary between the game and the rival model.

observations.py builds the only data that ever leaves the game: a short summary of what the
Regulator could see. tactics.py validates every reply. selector.py decides each encounter's
protocol (live, fixed schedule or neutral) and always falls back to the neutral tactic.
client.py talks to the rival service on a background thread with a hard deadline.
"""
