import os
import json
import subprocess
from itertools import permutations
from subprocess import CompletedProcess
from dataclasses import dataclass
from logger_setup import setup_grader_logger, _timestamp
from grader import DynamicGrader, DynamicGradeRunner, GradingResult
from typing import Any, Dict, List, Optional, Tuple, Union


def linear_score(
    acc_range: Tuple[int, int], score_range: Tuple[int, int], acc: float
) -> float:
    slope = (score_range[1] - score_range[0]) / (acc_range[1] - acc_range[0])
    return slope * (acc - acc_range[0]) + score_range[0]


@dataclass
class HW4Task2GradingResult(GradingResult):
    accuracy: Optional[float] = None
    reindexer: Optional[str] = None


class HW2Phase2LouvainDynamicGrader(DynamicGrader):
    def __init__(
        self,
        sandbox_dir: str,
        target_filename: str,
        command: List[str],
        gt_path: str = "p2_labels.csv",
        capture_output: bool = False,
    ):
        super().__init__(sandbox_dir, target_filename, command, capture_output)
        with open(gt_path) as fi:
            fi.readline()
            self.gt = {}
            for line in fi.readlines():
                id, category = line.split(",")
                id, category = int(id), int(category)
                self.gt[id] = category
        print(f"Loaded {len(self.gt)} ground truth labels")

    def run_command(
        self, sandbox_dir: str, command: List[str], capture_output: bool = False
    ):
        ret = subprocess.run(
            command,
            cwd=sandbox_dir,
            shell=True,
            timeout=15 * 60,  # 15 minutes
        )
        return ret

    def grade(self) -> GradingResult:
        try:
            ret = self.run_command(
                self.sandbox_dir,
                self.command,
                capture_output=self.capture_output,
            )
            res = self.process_result(self.sandbox_dir, ret)
        except subprocess.TimeoutExpired:
            return HW4Task2GradingResult(0.0, "Timeout", accuracy=None)
        return res

    def _load_file(self, filepath: str) -> Dict[str, Union[int, float]]:
        predictions = {}
        with open(filepath, encoding="utf-8") as fi:
            fi.readline()
            for line in fi.readlines():
                id, category = line.split(",")
                id, category = int(id), int(category)
                predictions[id] = category
        return predictions

    def process_result(self, sandbox_dir: str, ret: CompletedProcess) -> GradingResult:
        # locate file
        filepath = None
        for root, dirs, files in os.walk(sandbox_dir):
            for file in files:
                if file.endswith("p2_prediction.csv"):
                    filepath = os.path.join(root, file)
                    break
        if filepath is None:
            raise FileNotFoundError("p2_prediction.csv not found")

        res = self._load_file(filepath)

        n_clusters = len(set(res.values()))
        if n_clusters != 5:
            if n_clusters > 5 and n_clusters < 20:
                return HW4Task2GradingResult(
                    36.0, f"#classes != 5: {n_clusters}", accuracy=None
                )
            else:
                return HW4Task2GradingResult(
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
            return HW4Task2GradingResult(
                0.0, f"MANUAL: Accuracy {acc} < 20%", accuracy=None
            )

        score *= 0.6

        return HW4Task2GradingResult(
            score,
            message=None,
            accuracy=best_acc,
            reindexer="-".join(map(str, best_reindexer)),
        )


class HW2Phase2LouvainDynamicGradeRunner(DynamicGradeRunner):
    def sandbox_postinit(self):
        # copy data from data to sandbox_dir/p2_data
        dst_dir = os.path.join(self.sandbox_dir, "p2_data")
        self._overwrite_dir("data", dst_dir)


if __name__ == "__main__":
    META_NAME = "hw2p2-louvain-dynamic"
    # NOTE: this is the path in the docker container
    SANDBOX_DIR = "/root/ai3602/p2_CommunityDetection"
    BLACK_LIST = None
    WHITE_LIST = None

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-{META_NAME}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger(META_NAME, log_dir=log_dir)

    grader = HW2Phase2LouvainDynamicGrader(
        SANDBOX_DIR,
        "run.sh",
        ["bash run.sh"],
        capture_output=False,  # we dont need to capture output, results will be logged
    )
    runner = HW2Phase2LouvainDynamicGradeRunner(
        SANDBOX_DIR,
        logger,
        while_list=WHITE_LIST,
        black_list=BLACK_LIST,
    )

    res = runner.grade(
        grader,
        workdir="./student_files",
        ignore_dirs=[
            "logs",
            "zips",
            "data",
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
