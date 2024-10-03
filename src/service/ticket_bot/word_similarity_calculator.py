from typing import Iterable
import math


class Vector:
    def __init__(self, word: str) -> None:
        self.word_count = self._word_count(word)
        self.word_set = set(word)
        self.word_length = math.sqrt(
            sum(count * count for count in self.word_count.values())
        )

    def _word_count(self, word: str) -> dict[str, int]:
        count_map = {}
        for char in word:
            if char not in count_map:
                count_map[char] = 0
            count_map[char] += 1
        return count_map


class WordSimilarityCalculator:
    def __init__(self, checked_word: str, word_pool: Iterable[str]) -> None:
        self.checked_word_vector = Vector(checked_word)
        self.word_pool = word_pool

        self.similarity_map = self._calculate_cosin_distances()

    def _calculate_cosin_distances(self) -> dict[str, float]:
        # cosin_distance between checked_word and _other word
        simlarity_map = {}
        for word in self.word_pool:
            if len(word) == 0:
                continue
            word_vector = Vector(word)
            # which characters are common to the two words?
            common_word = self.checked_word_vector.word_set.intersection(
                word_vector.word_set
            )
            # by definition of cosine distance we have
            distance = (
                sum(
                    self.checked_word_vector.word_count[char]
                    * word_vector.word_count[char]
                    for char in common_word
                )
                / self.checked_word_vector.word_length
                / word_vector.word_length
            )
            simlarity_map[word] = distance

        return simlarity_map

    def highest_similarity(self) -> str:
        return max(self.similarity_map, key=lambda k: self.similarity_map.get(k, 0.0))
