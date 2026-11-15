"""Use a single agent instead of the whole team: review a file.

    python examples/review_my_code.py path/to/file.py
"""
import sys
from pathlib import Path

from apex.agents.base import ReviewerAgent

code = Path(sys.argv[1]).read_text(encoding="utf-8")
review = ReviewerAgent().run({"code": code})
print(f"verdict: {review.verdict}  score: {review.score}/100")
for issue in review.critical:
    print(" -", issue)
