"""Aurora professor loop: diagnose, train on measured weak points, verify on unseen exams.

One machine trains, another one examines. A candidate is described as improved
only when a paired comparison on held-out items says so; a training loss, a
transport receipt or a finished notebook is never evidence of quality.
"""

SCHEMA = 1
