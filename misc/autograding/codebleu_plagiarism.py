import os
import ast
import json
import pprint
from logging import Logger
from codebleu import evaluate_per_example
from logger_setup import setup_grader_logger, _timestamp
from typing import Dict, List, Tuple


class FunctionLocator(ast.NodeVisitor):
    def __init__(self, funcname: str):
        self.funcname = funcname
        self.found = False
        self.funcroot = None

    def visit_FunctionDef(self, node):
        if node.name == self.funcname:
            self.found = True
            self.funcroot = node
        self.generic_visit(node)


def locate_function(subdir: str, filename: str, funcname: str) -> str:
    filepath = None
    for root, dirs, files in os.walk(subdir):
        for file in files:
            if file == filename:
                filepath = os.path.join(root, file)
                break
    if filepath is None:
        raise FileNotFoundError(f"File {filename} not found in {subdir}")

    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    locator = FunctionLocator(funcname)
    locator.visit(tree)
    if not locator.found:
        raise ValueError(f"Function {funcname} not found in {filepath}")

    func_code = ast.unparse(locator.funcroot)
    return func_code


def pairwise_codebleu(
    stuname: str,
    workdir: str,
    funcs_to_check: List[Tuple[str, str]],
    ignore_dirs: List[str],
    logger: Logger,
) -> Dict[str, float]:
    codebleus = {}
    stu_codes = {}

    stupath = os.path.join(workdir, stuname)
    for filename, funcname in funcs_to_check:
        try:
            code = locate_function(stupath, filename, funcname)
            stu_codes[funcname] = code
        except Exception as e:
            logger.error(f"Error in {stupath}/{filename}/{funcname}: {e}")
            stu_codes[funcname] = None

    for othername in os.listdir(workdir):
        otherpath = os.path.join(workdir, othername)
        if (
            not os.path.isdir(otherpath)
            or othername in ignore_dirs
            or stuname == othername
        ):
            continue

        other_codes = {}
        for filename, funcname in funcs_to_check:
            try:
                code = locate_function(otherpath, filename, funcname)
                other_codes[funcname] = code
            except Exception as e:
                logger.error(f"Error in {otherpath}/{filename} ({funcname}): {e}")
                other_codes[funcname] = None

        codebleu = 0
        n_samples = 0
        for filename, funcname in funcs_to_check:
            if stu_codes[funcname] is None or other_codes[funcname] is None:
                continue

            stu_code = stu_codes[funcname]
            other_code = other_codes[funcname]
            codebleu += evaluate_per_example(stu_code, other_code)["codebleu"]
            n_samples += 1

        if n_samples > 0:
            codebleu /= n_samples

        codebleus[othername] = codebleu

    return codebleus


def main():
    WORKDIR = "./student_files"
    IGNORE_DIRS = [
        "logs",
        "zips",
        "data",
        "parser",
        "grader",
        "codebleu",
        "sandbox",
        "__pycache__",
    ]
    FUNCS_TO_CHECK = [
        ("loss.py", "forward"),
        ("model.py", "code_features"),
        ("method_invocation_visitor.py", "_dfs_method_invocation"),
    ]
    THRESHOLD = 0.85
    WHILE_LIST = ["521030910380孔子健", "520030910391庞小易"]

    timestamp = _timestamp()
    log_dir = f"logs/{timestamp}-codebleu-late"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = setup_grader_logger("codebleu", log_dir=log_dir)

    all_codebleus = {}
    for stuname in os.listdir(WORKDIR):
        stupath = os.path.join(WORKDIR, stuname)
        if not os.path.isdir(stupath) or stuname in IGNORE_DIRS:
            continue
        if stuname not in WHILE_LIST:
            continue

        logger.info(f"Scanning {stupath}")

        res = pairwise_codebleu(stuname, WORKDIR, FUNCS_TO_CHECK, IGNORE_DIRS, logger)
        all_codebleus[stuname] = res

    groups = dict()
    for stuname, codebleus in all_codebleus.items():
        topks = sorted(codebleus.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info(f"{stuname:25}: {topks}")
        for othername, codebleu in topks:
            if codebleu >= THRESHOLD:
                groupname = f"{stuname}-{othername}"
                groups[groupname] = codebleu
    logger.warning(pprint.pformat(groups))

    json_path = os.path.join(log_dir, "codebleu-groups.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(groups, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
