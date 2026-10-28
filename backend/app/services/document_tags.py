"""Expose existing automatic labels without changing or generating them."""
import json

DIFFICULTIES = ('基础', '进阶', '困难')


def _labels(value, maximum, length):
    if not isinstance(value, list):
        return []
    labels = []
    for item in value:
        if isinstance(item, str):
            label = item.strip()[:length]
            if label and label not in labels:
                labels.append(label)
            if len(labels) >= maximum:
                break
    return labels


def tags_of(doc):
    try:
        data = json.loads(doc.tags_json) if doc.tags_json else {}
    except (ValueError, TypeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    difficulty = doc.difficulty if doc.difficulty in DIFFICULTIES else data.get('difficulty')
    return {
        'knowledge_points': _labels(data.get('knowledge_points'), 6, 40),
        'question_types': _labels(data.get('question_types'), 5, 24),
        'difficulty': difficulty if difficulty in DIFFICULTIES else None,
    }
