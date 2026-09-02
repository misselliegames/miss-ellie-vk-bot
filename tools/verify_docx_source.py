from __future__ import annotations

import re
import sys

from docx import Document

from questions_3_4 import QUESTIONS_3_4
from questions_5_6 import QUESTIONS_5_6


def flat_lines(path):
    lines = []
    for paragraph in Document(path).paragraphs:
        lines.extend(line.strip() for line in paragraph.text.splitlines() if line.strip())
    return lines


def question_blocks(path):
    lines = flat_lines(path)
    starts = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\d+)\.\s", line)
        if match and 1 <= int(match.group(1)) <= 20:
            starts.append((int(match.group(1)), index))
    blocks = {}
    for position, (number, start) in enumerate(starts):
        end = starts[position + 1][1] if position + 1 < len(starts) else len(lines)
        blocks[number] = lines[start:end]
    return blocks


def verify(path, questions):
    blocks = question_blocks(path)
    if sorted(blocks) != list(range(1, 21)):
        raise AssertionError(f"Could not identify all 20 blocks in {path}: {sorted(blocks)}")
    for question in questions:
        block = blocks[question["id"]]
        question_lines = [line.strip() for line in question["question"].splitlines() if line.strip()]
        question_matches = any(
            block[index:index + len(question_lines)] == question_lines
            for index in range(len(block) - len(question_lines) + 1)
        )
        if not question_matches:
            raise AssertionError(
                f"Q{question['id']} question differs from DOCX: {question['question']!r}"
            )
        for option in question["options"]:
            if not any(line.startswith(option["text"]) for line in block):
                raise AssertionError(
                    f"Q{question['id']} option differs from DOCX: {option['text']!r}"
                )
    print(f"{path}: 20 questions and 60 options match exactly")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_docx_source.py GRADES_3_4.docx GRADES_5_6.docx")
    verify(sys.argv[1], QUESTIONS_3_4)
    verify(sys.argv[2], QUESTIONS_5_6)


if __name__ == "__main__":
    main()
