import os
from subprocess import CompletedProcess
from logger_setup import setup_grader_logger, _timestamp
from grader import DynamicGrader, DynamicGradeRunner, GradingResult
from typing import Any, Dict


class HW2Phase2ModularityDynamicGrader(DynamicGrader):
    def process_result(self, sandbox_dir: str, ret: CompletedProcess) -> Dict[str, Any]:
        if ret is None or ret.stderr is None:
            return GradingResult(score=None, message="No output")

        # for some reason result is logged in stderr
        stdout = ret.stderr.decode()
        if "OK" in stdout:
            return GradingResult(score=20)
        else:
            lines = stdout.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("========"):
                    break
            res_line = lines[i - 1]

            # count "."'s in result line
            n_corrects = res_line.count(".")
            return GradingResult(score=n_corrects * (20 / 10))


class HW2Phase2ModularityDynamicGradeRunner(DynamicGradeRunner):
    def sandbox_postinit(self):
        # copy data from data to sandbox_dir/data
        dst_dir = os.path.join(self.sandbox_dir, "p2_data")
        self._overwrite_dir("data", dst_dir)

        # copy "test_modularity_reserve.py" to sandbox_dir
        dst_path = os.path.join(self.sandbox_dir, "test_modularity_reserve.py")
        self._overwrite_file("test_modularity_reserve.py", dst_path)


if __name__ == "__main__":
    META_NAME = "hw2p2-modularity-dynamic"
    SANDBOX_DIR = "sandbox"
    BLACK_LIST = None
    WHITE_LIST = None

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-{META_NAME}"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger(META_NAME, log_dir=log_dir)

    grader = HW2Phase2ModularityDynamicGrader(
        SANDBOX_DIR,
        "p2_main.py",
        ["python test_modularity_reserve.py"],
        capture_output=True,
    )
    runner = HW2Phase2ModularityDynamicGradeRunner(
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
