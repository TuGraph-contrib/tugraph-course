import os
import csv
import json
import logging
from .grading_result import GradingResult
from typing import List, Dict, Optional


class StaticGrader:
    def __init__(self, target_filename: str):
        self.target_filename = target_filename

    def grade(self, filepath: str) -> GradingResult:
        raise NotImplementedError("Subclasses must implement this method")


class StaticGradeRunner:
    def __init__(self, logger: logging.Logger):
        self.results: Dict[str, GradingResult] = {}
        self.logger = logger

    def locate_file(self, subdir: str, filename: str) -> str:
        for root, dirs, files in os.walk(subdir):
            for file in files:
                if file == filename:
                    return os.path.join(root, file)

        raise FileNotFoundError(f"File {filename} not found in {subdir}")

    def grade(
        self,
        grader: StaticGrader,
        workdir: str,
        ignore_dirs: Optional[List[str]] = None,
    ):
        if ignore_dirs is None:
            ignore_dirs = []

        n_success = 0
        n_failure = 0
        failed_studirs = list()
        for studir in sorted(os.listdir(workdir)):
            if studir in ignore_dirs:
                continue
            if not os.path.isdir(os.path.join(workdir, studir)):
                continue

            self.logger.info(f"Grading {studir}")
            studir_path = os.path.join(workdir, studir)

            # grade the file with each grader
            try:
                target_filename = grader.target_filename
                filepath = self.locate_file(studir_path, target_filename)
                grader_res = grader.grade(filepath)
            except Exception as e:
                self.logger.error(f"Error grading {studir}: {e}")
                grader_res = GradingResult(None, str(e))
                failed_studirs.append(studir)
                n_failure += 1
            else:
                n_success += 1

            self.results[studir] = grader_res
            self.logger.info(f"Result for {studir}: {grader_res}")

        self.logger.info("Grading complete")
        tot_processed = n_success + n_failure
        self.logger.info(
            f"Processed {tot_processed} files, "
            f"{n_success} successful, {n_failure} failed"
        )
        self.logger.info(f"Failed students: {failed_studirs}")
        return self.results

    def write_csv(self, results: Dict[str, GradingResult], outpath: str):
        with open(outpath, "w", newline="") as f:
            writer = csv.writer(f)
            schema = next(iter(results.values())).get_schema()
            writer.writerow(["student"] + schema)
            for student, res in results.items():
                res = res.to_dict()
                writer.writerow([student] + [res.get(k, None) for k in schema])

    def dump_json(self, results: Dict[str, GradingResult], outpath: str):
        dumped = {k: v.to_dict() for k, v in results.items()}
        with open(outpath, "w") as f:
            json.dump(dumped, f, indent=2, ensure_ascii=False)
