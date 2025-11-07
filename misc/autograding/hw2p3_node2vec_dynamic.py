import os
from dataclasses import dataclass
from sklearn.metrics import roc_curve
from sklearn.metrics import auc
from subprocess import CompletedProcess
from logger_setup import setup_grader_logger, _timestamp
from grader import DynamicGrader, DynamicGradeRunner, GradingResult
from typing import Any, Dict, List, Optional, Tuple, Union


def calc_auc_score(predictions, truth):
    """
    A simple function for calculating the AUC score.

    XXX: Do not change this function.
    """
    fpr, tpr, th = roc_curve(truth, predictions)
    return auc(fpr, tpr)


def linear_score(
    acc_range: Tuple[int, int], score_range: Tuple[int, int], acc: float
) -> float:
    slope = (score_range[1] - score_range[0]) / (acc_range[1] - acc_range[0])
    return slope * (acc - acc_range[0]) + score_range[0]


@dataclass
class HW2Phase3Node2VecGradingResult(GradingResult):
    auc_score: Optional[float] = None


class HW2Phase3Node2VecDynamicGrader(DynamicGrader):
    def __init__(
        self,
        sandbox_dir: str,
        target_filename: str,
        command: List[str],
        gt_path: str = "p3_truths.csv",
        capture_output: bool = False,
    ):
        super().__init__(sandbox_dir, target_filename, command, capture_output)
        self.gt = {}
        with open(gt_path) as fi:
            fi.readline()
            for line in fi.readlines():
                id, label = line.split(",")
                id, label = int(id), float(label)
                self.gt[id] = label
        print(f"Loaded {len(self.gt)} ground truth labels")

    def _load_file(self, filepath: str) -> Dict[str, float]:
        predictions = {}
        with open(filepath, encoding="utf-8") as fi:
            fi.readline()
            for line in fi.readlines():
                id, label = line.split(",")
                id, label = int(id), float(label)
                predictions[id] = label
        return predictions

    def process_result(self, sandbox_dir: str, ret: CompletedProcess) -> Dict[str, Any]:
        # locate file
        for root, dirs, files in os.walk(sandbox_dir):
            for file in files:
                if file.endswith("p3_prediction.csv"):
                    filepath = os.path.join(root, file)
                    break

        res = self._load_file(filepath)

        preds = []
        gts = []
        for i in range(len(res)):
            preds.append(res[i])
            gts.append(self.gt[i])
        auc_score = calc_auc_score(preds, gts)

        if auc_score >= 0.93:
            score = 60
        elif auc_score >= 0.85:
            score = linear_score((0.85, 0.93), (50, 60), auc_score)
        elif auc_score >= 0.75:
            score = linear_score((0.75, 0.85), (40, 50), auc_score)
        elif auc_score >= 0.65:
            score = linear_score((0.65, 0.75), (20, 40), auc_score)
        else:
            return HW2Phase3Node2VecGradingResult(
                score=0, message="AUC score too low", auc_score=auc_score
            )

        return HW2Phase3Node2VecGradingResult(score=score, auc_score=auc_score)


class HW2Phase2Node2VecDynamicGradeRunner(DynamicGradeRunner):
    def sandbox_postinit(self):
        # copy data from data to sandbox_dir/data
        dst_dir = os.path.join(self.sandbox_dir, "p3_data")
        self._overwrite_dir("p3_data", dst_dir)


if __name__ == "__main__":
    META_NAME = "hw2p3-node2vec-dynamic-late"
    # NOTE: this is the path in the docker container
    SANDBOX_DIR = "/root/ai3602/p3_LinkPrediction"
    # code are buggy and jams grading script
    BLACK_LIST = ["520030910343查清哲", "520030910360何嘉明"]
    WHITE_LIST = None

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-{META_NAME}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger(META_NAME, log_dir=log_dir)

    grader = HW2Phase3Node2VecDynamicGrader(
        SANDBOX_DIR,
        "run.sh",
        ["bash run.sh"],
        capture_output=False,  # we dont need to capture output, results will be logged
    )
    runner = HW2Phase2Node2VecDynamicGradeRunner(
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
            "p3_data",
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
