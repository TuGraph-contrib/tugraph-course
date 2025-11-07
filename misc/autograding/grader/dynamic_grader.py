import os
import sys
import csv
import json
import shutil
import logging
import subprocess
from .grading_result import GradingResult
from typing import List, Dict, Optional


class DynamicGrader:
    def __init__(
        self,
        sandbox_dir: str,
        target_filename: str,
        command: List[str],
        capture_output: bool = False,
        timeout: Optional[int] = None,
    ):
        self.sandbox_dir = sandbox_dir
        self.target_filename = target_filename
        self.command = command
        self.capture_output = capture_output
        self.timeout = timeout

    def get_schema(self) -> List[str]:
        raise NotImplementedError("Subclasses must implement this method")

    def grade(self) -> GradingResult:
        ret = self.run_command(
            self.sandbox_dir,
            self.command,
            timeout=self.timeout,
            capture_output=self.capture_output,
        )
        res = self.process_result(self.sandbox_dir, ret)
        return res

    def run_command(
        self,
        sandbox_dir: str,
        command: List[str],
        timeout: Optional[int] = None,
        capture_output: bool = False,
    ):
        if sys.version_info >= (3, 7):
            ret = subprocess.run(
                command,
                cwd=sandbox_dir,
                shell=True,
                capture_output=capture_output,
                timeout=timeout,
            )
        else:
            ret = subprocess.run(
                command,
                cwd=sandbox_dir,
                shell=True,
                timeout=timeout,
            )
        return ret

    def process_result(
        self,
        sandbox_dir: str,
        ret: subprocess.CompletedProcess,
    ) -> GradingResult:
        raise NotImplementedError("Subclasses must implement this method")


class DynamicGradeRunner:
    def __init__(
        self,
        sandbox_dir: str,
        logger: logging.Logger,
        while_list: List[str] = None,
        black_list: List[str] = None,
    ):
        self.results: Dict[str, Dict] = {}
        self.logger = logger
        self.sandbox_dir = sandbox_dir
        self.white_list = while_list
        self.black_list = black_list

    def _locate_src_dir(self, subdir: str, entry_file: str) -> str:
        for root, dirs, files in os.walk(subdir):
            for file in files:
                if file == entry_file:
                    return root

        raise FileNotFoundError(f"File {entry_file} not found in {subdir}")

    def _overwrite_file(self, src_file: str, dest_file: str):
        shutil.copyfile(src_file, dest_file)

    def _overwrite_dir(self, src_dir: str, dest_dir: str):
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)

    def _clear_dir(self, dirpath: str):
        if os.path.exists(dirpath):
            shutil.rmtree(dirpath)
        os.makedirs(dirpath)

    def init_sandbox(self, sandbox_dir: str, src_dir: str):
        """
        Prepare a sandbox directory for running the grading command.
        Clear the sandbox directory if it already exists.
        Then copy all files from src_dir to sandbox_dir.
        """
        if os.path.exists(sandbox_dir):
            shutil.rmtree(sandbox_dir)
        # os.makedirs(sandbox_dir)

        # copy files from src_dir to sandbox_dir
        shutil.copytree(src_dir, sandbox_dir)
        self.logger.info(f"Initialized sandbox {sandbox_dir} with {src_dir}")

    def sandbox_postinit(self):
        """
        Post-processing steps after the initial files are copied to sandbox.
        Typically overwrite the dataset files and unittest files.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def grade(
        self,
        grader: DynamicGrader,
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
            if self.white_list is not None and studir not in self.white_list:
                continue
            if self.black_list is not None and studir in self.black_list:
                continue

            self.logger.info(f"Grading {studir}")
            studir_path = os.path.join(workdir, studir)

            try:
                anchor_file = grader.target_filename
                src_dir = self._locate_src_dir(studir_path, anchor_file)
                self.init_sandbox(self.sandbox_dir, src_dir)
                self.sandbox_postinit()
                grader_res = grader.grade()
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
