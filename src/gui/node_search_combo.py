"""Editable, ranked node selector for large graph datasets."""

import heapq
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QComboBox, QCompleter


_NON_WORDS = re.compile(r"[^\w]+", re.UNICODE)


def normalize_search_text(value):
    """Normalize case, accents and punctuation for Vietnamese-friendly search."""
    value = str(value or "").casefold().replace("đ", "d")
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(_NON_WORDS.sub(" ", value).split())


def _trigrams(value):
    compact = value.replace(" ", "")
    if len(compact) < 3:
        return set()
    return {compact[index : index + 3] for index in range(len(compact) - 2)}


@dataclass(frozen=True)
class _SearchEntry:
    node_id: str
    display: str
    normalized_id: str
    normalized_name: str
    normalized_display: str


class NodeSearchIndex:
    """Precomputed normalized search data that multiple fields can share."""

    def __init__(self, entries=()):
        indexed_entries = []
        gram_index = defaultdict(list)
        for index, (node_id, name, display) in enumerate(entries):
            entry = _SearchEntry(
                node_id=str(node_id),
                display=str(display),
                normalized_id=normalize_search_text(node_id),
                normalized_name=normalize_search_text(name),
                normalized_display=normalize_search_text(display),
            )
            indexed_entries.append(entry)
            for gram in _trigrams(entry.normalized_display):
                gram_index[gram].append(index)
        self.entries = tuple(indexed_entries)
        self.entries_by_id = {
            entry.node_id: entry for entry in indexed_entries
        }
        self.gram_index = dict(gram_index)


class NodeSearchComboBox(QComboBox):
    """A combo-box-compatible field that only renders ranked suggestions.

    The full node model remains attached to the combo so existing callers can
    continue using ``findData`` and ``setCurrentIndex``. Search results use a
    separate, capped model, avoiding construction of a popup with thousands of
    rows on every keystroke.
    """

    SUGGESTION_LIMIT = 12
    SEARCH_DELAY_MS = 90
    FUZZY_CANDIDATE_LIMIT = 200

    def __init__(self, parent=None, placeholder="Gõ ID hoặc tên node..."):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(12)
        self.lineEdit().setPlaceholderText(placeholder)
        self.lineEdit().setClearButtonEnabled(True)

        self._search_index = NodeSearchIndex()
        self._visible_suggestion_ids = []

        self._suggestion_model = QStandardItemModel(self)
        self._search_completer = QCompleter(self._suggestion_model, self)
        self._search_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._search_completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self._search_completer.setMaxVisibleItems(self.SUGGESTION_LIMIT)
        self._search_completer.popup().setObjectName("nodeSuggestions")
        self._search_completer.popup().setUniformItemSizes(True)
        self.setCompleter(self._search_completer)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(self.SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._refresh_suggestions)
        self.lineEdit().textEdited.connect(self._queue_search)
        self.lineEdit().returnPressed.connect(self.commit_best_match)
        self._search_completer.activated[str].connect(self._commit_suggestion)

    def setModel(self, model):
        """Keep the completer on its small result model when choices reload."""
        super().setModel(model)
        if hasattr(self, "_search_completer"):
            self._search_completer.setModel(self._suggestion_model)

    def currentData(self, role=Qt.UserRole):
        """Return no stale selection while the user has uncommitted text."""
        index = super().currentIndex()
        if index < 0 or self.lineEdit().text() != super().itemText(index):
            return None
        return super().itemData(index, role)

    def set_search_entries(self, entries):
        """Build the reusable normalized and trigram indexes once per dataset."""
        self.set_search_index(NodeSearchIndex(entries))

    def set_search_index(self, search_index):
        """Reuse a prebuilt index across Start and Goal fields."""
        if not isinstance(search_index, NodeSearchIndex):
            raise TypeError("search_index must be a NodeSearchIndex")
        self._search_index = search_index
        self._clear_suggestions()

    def ranked_node_ids(self, query, limit=None):
        """Return node IDs ordered by textual relevance.

        Exact, prefix, token and substring matches are preferred. A small
        trigram shortlist then supplies typo-tolerant fuzzy matches.
        """
        limit = self.SUGGESTION_LIMIT if limit is None else max(0, int(limit))
        if not limit:
            return []
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            return []

        query_tokens = normalized_query.split()
        direct_scores = []
        direct_indexes = set()
        for index, entry in enumerate(self._search_index.entries):
            score = self._direct_score(entry, normalized_query, query_tokens, index)
            if score is not None:
                direct_scores.append((score, index))
                direct_indexes.add(index)

        ranked = heapq.nsmallest(limit, direct_scores)
        if len(ranked) < limit:
            ranked.extend(
                self._fuzzy_matches(
                    normalized_query,
                    direct_indexes,
                    limit - len(ranked),
                )
            )
        return [
            self._search_index.entries[index].node_id
            for _score, index in ranked
        ]

    @staticmethod
    def _direct_score(entry, query, query_tokens, index):
        if query == entry.normalized_id:
            return (0, 0, len(entry.normalized_display), index)
        if query == entry.normalized_name:
            return (0, 1, len(entry.normalized_display), index)
        if entry.normalized_id.startswith(query):
            return (1, len(entry.normalized_id), 0, index)
        if entry.normalized_name.startswith(query):
            return (2, len(entry.normalized_name), 0, index)

        words = entry.normalized_display.split()
        if any(word.startswith(query) for word in words):
            prefix_position = min(
                word.find(query) for word in words if word.startswith(query)
            )
            return (3, prefix_position, len(words), index)
        if query in entry.normalized_id:
            return (
                4,
                entry.normalized_id.find(query),
                len(entry.normalized_id),
                index,
            )
        if query in entry.normalized_name:
            return (
                5,
                entry.normalized_name.find(query),
                len(entry.normalized_name),
                index,
            )
        if len(query_tokens) > 1 and all(
            token in entry.normalized_display for token in query_tokens
        ):
            return (
                6,
                sum(entry.normalized_display.find(token) for token in query_tokens),
                len(entry.normalized_display),
                index,
            )
        return None

    def _fuzzy_matches(self, query, excluded_indexes, limit):
        query_grams = _trigrams(query)
        if not query_grams or not limit:
            return []

        overlap_counts = Counter()
        for gram in query_grams:
            overlap_counts.update(self._search_index.gram_index.get(gram, ()))
        candidates = heapq.nlargest(
            self.FUZZY_CANDIDATE_LIMIT,
            (index for index in overlap_counts if index not in excluded_indexes),
            key=lambda index: (
                overlap_counts[index] / len(query_grams),
                -abs(
                    len(self._search_index.entries[index].normalized_name)
                    - len(query)
                ),
            ),
        )

        fuzzy_scores = []
        for index in candidates:
            entry = self._search_index.entries[index]
            similarity = max(
                SequenceMatcher(None, query, entry.normalized_id).ratio(),
                SequenceMatcher(None, query, entry.normalized_name).ratio(),
            )
            if similarity >= 0.34:
                score = (
                    7,
                    -similarity,
                    abs(len(entry.normalized_name) - len(query)),
                    index,
                )
                fuzzy_scores.append(
                    (score, index)
                )
        return heapq.nsmallest(limit, fuzzy_scores)

    def _queue_search(self, _text):
        self._search_timer.start()

    def _refresh_suggestions(self):
        query = self.lineEdit().text()
        node_ids = self.ranked_node_ids(query)
        self._suggestion_model.clear()
        self._visible_suggestion_ids = node_ids

        for node_id in node_ids:
            entry = self._search_index.entries_by_id[node_id]
            item = QStandardItem(entry.display)
            item.setData(node_id, Qt.UserRole)
            self._suggestion_model.appendRow(item)

        self._search_completer.setCompletionPrefix("")
        if node_ids and (self.hasFocus() or self.lineEdit().hasFocus()):
            self._search_completer.complete()
        else:
            self._search_completer.popup().hide()

    def _clear_suggestions(self):
        self._search_timer.stop()
        self._suggestion_model.clear()
        self._visible_suggestion_ids = []
        self._search_completer.popup().hide()

    def _commit_suggestion(self, display_text):
        for row in range(self._suggestion_model.rowCount()):
            item = self._suggestion_model.item(row)
            if item.text() == display_text:
                self.select_node(item.data(Qt.UserRole))
                return

    def commit_best_match(self):
        """Commit the highest-ranked visible/query result, if one exists."""
        current_index = super().currentIndex()
        if (
            current_index >= 0
            and self.lineEdit().text() == super().itemText(current_index)
        ):
            return True
        node_ids = self.ranked_node_ids(self.lineEdit().text(), limit=1)
        return bool(node_ids) and self.select_node(node_ids[0])

    def select_node(self, node_id):
        index = self.findData(node_id, Qt.UserRole)
        if index < 0:
            return False
        self.setCurrentIndex(index)
        self.lineEdit().setText(self.itemText(index))
        self._clear_suggestions()
        return True

    def showPopup(self):
        """Turn arrow clicks into edit focus instead of a huge full-node popup."""
        if not self.isEnabled():
            return
        self.lineEdit().setFocus(Qt.MouseFocusReason)
        self.lineEdit().selectAll()

    def hidePopup(self):
        super().hidePopup()
        if hasattr(self, "_search_completer"):
            self._search_completer.popup().hide()
