#!/usr/bin/env python

import os
import subprocess
import sys

def make_next_version():
    final_compiler = meta_compile_rlmeta()
    test(final_compiler)
    mv(final_compiler, "rlmeta.py")

def meta_compile_rlmeta():
    compiler = "rlmeta.py"
    content = read(compiler)
    for i in range(4):
        next_compiler = "rlmeta{}.py".format(i+1)
        next_content = compile_rlmeta(compiler)
        log("Writing {}".format(next_compiler))
        write(next_compiler, next_content)
        if next_content == content:
            return next_compiler
        compiler = next_compiler
        content = next_content
    fail("Unable to produce metacompiler.")

def compile_rlmeta(rlmeta):
    log("Compiling rlmeta using {}".format(rlmeta))
    return run_rlmeta(rlmeta, [
        "--embed", "SUPPORT", "src/support.py",
        "--support",
        "--compile", "src/parser.rlmeta",
        "--compile", "src/codegenerator.rlmeta",
        "--copy", "src/main.py",
    ])

def test(rlmeta):
    log("Test: Has its own support library")
    assert run_rlmeta(rlmeta, ["--support"]) == read("src/support.py")
    log("Test: Disallow semantic action in the middle")
    run_rlmeta(rlmeta, [], b"Grammar { x = . -> [] . }", expect_failure=True)
    log("Test: Call unknown rule foo")
    assert test_grammar(
        rlmeta,
        b"Grammar { x = % | . }",
        b"print(compile_chain(['Grammar.x'], ['foo']))"
    ) == b"foo\n"

def test_grammar(rlmeta, grammar, main_code):
    compiled = run_rlmeta(rlmeta, ["--support", "--compile", "-"], grammar)
    total = compiled + main_code
    process = subprocess.Popen(
        ["python"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    stdout, _ = process.communicate(total)
    return stdout

def run_rlmeta(rlmeta, args, stdin=b"", expect_failure=False):
    process = subprocess.Popen(
        ["python", rlmeta]+args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    stdout, _ = process.communicate(stdin)
    if expect_failure:
        if process.returncode == 0:
            fail("Expected failure")
    else:
        if process.returncode != 0:
            fail("Expected success")
    return stdout

def mv(src, dest):
    log("Moving {} -> {}".format(src, dest))
    os.remove(dest)
    os.rename(src, dest)

def cleanup():
    for path in [
        "rlmeta1.py",
        "rlmeta2.py",
        "rlmeta3.py",
        "rlmeta4.py",
    ]:
        if os.path.exists(path):
            log("Deleting {}".format(path))
            os.remove(path)

def read(path):
    with open(path, "rb") as f:
        return f.read()

def write(path, content):
    with open(path, "wb") as f:
        return f.write(content)

def log(message):
    sys.stderr.write(color(f"{message}\n", "33"))

def success(message):
    sys.stderr.write(color(f"{message}\n", "32"))

def fail(message):
    sys.exit(color(f"ERROR: {message}", "31"))

def color(message, color):
    if os.isatty(sys.stderr.fileno()):
        return f"\033[0;{color}m{message}\033[0m"
    else:
        return message

if __name__ == "__main__":
    cleanup()
    if sys.argv[1:] == ["--compile"]:
        sys.stdout.buffer.write(compile_rlmeta("rlmeta.py"))
    else:
        make_next_version()
    cleanup()
    success("  O-----------------O")
    success("  | RLMeta compiled |")
    success("~~|     itself!     |")
    success("  O-----------------O")
