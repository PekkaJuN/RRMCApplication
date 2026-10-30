"""The prompt, the answer schema and answer parsing, shared by every variant (PC4).

They are the app's own (receipt-reading PC11); only the image prompt is the tool's.
"""

from app.receipt_reading.prompt import ANSWER_SCHEMA as ANSWER_SCHEMA
from app.receipt_reading.prompt import INSTRUCTIONS
from app.receipt_reading.prompt import Answer as Answer
from app.receipt_reading.prompt import AnswerLine as AnswerLine
from app.receipt_reading.prompt import parse_answer as parse_answer
from app.receipt_reading.prompt import text_prompt as text_prompt


def image_prompt() -> str:
    return f"{INSTRUCTIONS}\nThe receipt is in the attached image.\n"
