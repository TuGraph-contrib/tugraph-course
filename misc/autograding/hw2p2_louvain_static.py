import os
import json
from itertools import permutations
from dataclasses import dataclass
from logger_setup import setup_grader_logger, _timestamp
from grader import GradingResult, StaticGrader, StaticGradeRunner
from typing import Dict, Optional, Tuple


def linear_score(
    acc_range: Tuple[int, int], score_range: Tuple[int, int], acc: float
) -> float:
    slope = (score_range[1] - score_range[0]) / (acc_range[1] - acc_range[0])
    return slope * (acc - acc_range[0]) + score_range[0]


@dataclass
class HW2P2LouvainGradingResult(GradingResult):
    accuracy: Optional[float] = None
    reindexer: Optional[str] = None


class HW2P2LouvainAccGrader(StaticGrader):
    def __init__(self, target_filename: str, gt_path: str = "p2_labels.csv"):
        super().__init__(target_filename)
        with open(gt_path) as fi:
            fi.readline()
            self.gt = {}
            for line in fi.readlines():
                id, category = line.split(",")
                id, category = int(id), int(category)
                self.gt[id] = category
        print(f"Loaded {len(self.gt)} ground truth labels")

    def _load_file(self, filepath: str) -> Dict[str, int | float]:
        predictions = {}
        with open(filepath, encoding="utf-8") as fi:
            fi.readline()
            for line in fi.readlines():
                id, category = line.split(",")
                id, category = int(id), int(category)
                predictions[id] = category
        return predictions

    def grade(self, filepath: str) -> HW2P2LouvainGradingResult:
        res = self._load_file(filepath)

        n_clusters = len(set(res.values()))
        if n_clusters != 5:
            if n_clusters > 5 and n_clusters < 20:
                return HW2P2LouvainGradingResult(
                    36.0, f"#classes != 5: {n_clusters}", accuracy=None
                )
            else:
                return HW2P2LouvainGradingResult(
                    0.0, f"MANUAL. #classes != 5: {n_clusters}", accuracy=None
                )

        best_acc = 0.0
        best_reindexer = (0,)
        for reindexer in permutations(range(5)):
            acc = 0.0
            for idx, lbl in self.gt.items():
                if reindexer[res[idx]] == lbl:
                    acc += 1
            acc /= len(self.gt)
            if acc > best_acc:
                best_acc = acc
                best_reindexer = reindexer
        acc = best_acc * 100

        if acc >= 70:
            score = 100
        elif acc >= 60:
            score = linear_score((60, 70), (90, 100), acc)
        elif acc >= 50:
            score = linear_score((50, 60), (80, 90), acc)
        elif acc >= 20:
            score = linear_score((20, 50), (60, 80), acc)
        else:
            return HW2P2LouvainGradingResult(
                0.0, f"MANUAL: Accuracy {acc} < 20%", accuracy=None
            )

        score *= 0.6

        return HW2P2LouvainGradingResult(
            score,
            message=None,
            accuracy=best_acc,
            reindexer="-".join(map(str, best_reindexer)),
        )


class HW4AutoGradeRunner(StaticGradeRunner):
    def locate_file(self, subdir: str, filename: str) -> str:
        candidates = []
        for root, dirs, files in os.walk(subdir):
            for file in files:
                if file.endswith(filename):
                    candidates.append((root, file))

        if len(candidates) == 0:
            raise FileNotFoundError(f"File {filename} not found in {subdir}")
        else:
            # sort in descending order of file name
            candidates.sort(key=lambda x: x[1], reverse=True)
            return os.path.join(candidates[0][0], candidates[0][1])


if __name__ == "__main__":
    META_NAME = "hw2p2-louvain-static"

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-{META_NAME}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger(META_NAME, log_dir=log_dir)

    grader = HW2P2LouvainAccGrader(target_filename="p2_prediction.csv")
    runner = HW4AutoGradeRunner(logger)

    res = runner.grade(
        grader,
        workdir="./student_files",
        ignore_dirs=[
            "logs",
            "zips",
            "data",
            "p2_data",
            "parser",
            "grader",
            "codebleu",
            "sandbox",
            "__pycache__",
        ],
    )
    runner.write_csv(res, f"{log_dir}/{META_NAME}.csv")
    runner.dump_json(res, f"{log_dir}/{META_NAME}.json")

    logger.info("Grading complete")
    logger.info(f"Results written to {log_dir}/{META_NAME}.csv and .json")
