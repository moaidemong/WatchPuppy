from __future__ import annotations


REVIEW_STATUS_OPTIONS = ["pending", "approved", "rejected"]

REVIEW_LABEL_OPTIONS = [
    "failed_get_up_attempt",
    "normal_standing",
    "normal_rest",
    "normal_movement",
    "human_interference",
    "other_animal",
    "unclear",
]

TEXT_TRANSLATIONS = {
    "save": "저장",
    "pending": "대기",
    "approved": "확정",
    "rejected": "기각",
    "failed_get_up_attempt": "기상 실패 시도",
    "normal_standing": "정상 기립",
    "normal_rest": "정상 휴식",
    "normal_movement": "정상 이동",
    "human_interference": "사람 개입",
    "other_animal": "다른 동물",
    "unclear": "애매함",
    "non_target": "비대상",
}
