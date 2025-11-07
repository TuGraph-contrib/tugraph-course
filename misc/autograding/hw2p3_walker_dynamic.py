import os
from dataclasses import dataclass
from subprocess import CompletedProcess
from logger_setup import setup_grader_logger, _timestamp
from grader import DynamicGrader, DynamicGradeRunner, GradingResult
from typing import Any, Dict, Optional


@dataclass
class HW2Phase3WalkerGradingResult(GradingResult):
    score_uniform: Optional[int] = None
    score_biased: Optional[int] = None


class HW2Phase3WalkerDynamicGrader(DynamicGrader):
    def process_result(
        self, sandbox_dir: str, ret: CompletedProcess
    ) -> HW2Phase3WalkerGradingResult:
        if ret.stderr is not None and len(ret.stderr) > 0:
            return HW2Phase3WalkerGradingResult(score=None, message=ret.stderr.decode())

        if ret is None or ret.stdout is None or len(ret.stdout) == 0:
            return HW2Phase3WalkerGradingResult(score=None, message="No output")

        # for some reason result is logged in stderr
        stdout = ret.stdout.decode()
        score_uniform, score_biased = int(stdout.split(",")[0]), int(stdout.split(",")[1])
        return HW2Phase3WalkerGradingResult(
            score=3 * score_uniform + score_biased,
            score_uniform=score_uniform,
            score_biased=score_biased,
        )


class HW2Phase3WalkerDynamicGradeRunner(DynamicGradeRunner):
    def sandbox_postinit(self):
        # copy data from data to sandbox_dir/data
        dst_dir = os.path.join(self.sandbox_dir, "p3_data")
        self._overwrite_dir("p3_data", dst_dir)

        # copy "test_random_walk.py" to sandbox_dir
        dst_path = os.path.join(self.sandbox_dir, "test_random_walk.py")
        self._overwrite_file("test_random_walk.py", dst_path)

        # copy reference data to sandbox_dir
        dst_path = os.path.join(self.sandbox_dir, "test_random_walk_references.json")
        self._overwrite_file("test_random_walk_references.json", dst_path)


if __name__ == "__main__":
    META_NAME = "hw2p3-walker-dynamic-late"
    # NOTE: this is the path in the docker container
    SANDBOX_DIR = "sandbox"
    BLACK_LIST = None
    WHITE_LIST = None

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-{META_NAME}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger(META_NAME, log_dir=log_dir)

    grader = HW2Phase3WalkerDynamicGrader(
        SANDBOX_DIR,
        "p3_main.py",
        ["python test_random_walk.py"],
        capture_output=True,
    )
    runner = HW2Phase3WalkerDynamicGradeRunner(
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
