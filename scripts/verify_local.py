"""KIC local one-command verification. No network, data deletion or repo writes.

Outputs PASS/FAIL/SKIP with logs to a newly created OS temp directory.
For Windows: .\verify_local.ps1 [-Full]
For shell: python -m scripts.verify_local [--full]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
TARGETS=[
    "tests.test_sec_bundle_replay",
    "tests.test_sec_capture_bundle",
    "tests.test_sec_three_source",
    "tests.test_local_sec_packet",
]


def _sha() -> tuple[str | None,str]:
    try:
        p=subprocess.run(
            ["git","rev-parse","HEAD"],cwd=ROOT,
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,check=False,timeout=5,
        )
        if p.returncode==0 and re.fullmatch(r"[0-9a-f]{40}",p.stdout.strip()):
            return p.stdout.strip(),"PASS"
    except (OSError,subprocess.TimeoutExpired):
        pass
    return None,"SKIP"


def main(argv=None) -> int:
    arg=argparse.ArgumentParser(description="Offline KIC quick/full verification")
    arg.add_argument("--full",action="store_true",help="Full suite instead of targeted core")
    args=arg.parse_args(argv)
    output=Path(tempfile.mkdtemp(prefix="kic-local-verify-"))
    sha,sha_state=_sha()
    details={"schema":"kic-local-verification.v1","environment":"local",
             "utc_started":datetime.now(timezone.utc).isoformat(),
             "source_sha":sha,"source_sha_check":sha_state,
             "mode":"full" if args.full else "quick",
             "syntax":{"status":"PASS","checked":0},
             "tests":{"status":"SKIP","executed":0,"failed":None,"skipped":None},
             "logs_dir":str(output)}
    try:
        if sys.version_info < (3,11):
            raise RuntimeError("PYTHON_3_11_REQUIRED")
        # Syntax without pycache: read-only across the entire source tree.
        for folder in ("proofinvest","disclosure_lightning","scripts","tests"):
            for path in (ROOT/folder).rglob("*.py"):
                compile(path.read_bytes(),str(path),"exec")
                details["syntax"]["checked"]+=1
        command=[sys.executable,"-B","-m","unittest"]
        if args.full:
            command.extend(["discover","-s","tests","-v"])
        else:
            command.extend([*TARGETS,"-v"])
        env=os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"]="1"
        # On Windows, force UTF-8 traceback output into the UTF-8 log.
        env["PYTHONIOENCODING"]="utf-8"
        # No real services, credentials, DB, or network are required by these tests.
        testlog=output/"tests.log"
        with testlog.open("x",encoding="utf-8") as log:
            process=subprocess.run(
                command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                text=True,check=False,timeout=240,
            )
        text=testlog.read_text(encoding="utf-8",errors="replace")
        count=re.search(r"Ran ([0-9]+) tests?",text)
        skips=re.search(r"OK \(skipped=([0-9]+)\)",text)
        failed_line=re.search(r"(?m)^FAILED \(([^\n]+)\)$",text)
        failure_counts=dict(
            (key,int(value)) for key,value in
            re.findall(r"(\w+)=([0-9]+)",failed_line.group(1))
        ) if failed_line else {}
        executed=int(count.group(1)) if count else None
        passed=(process.returncode==0 and executed is not None and executed>0)
        n_fail=failure_counts.get("failures",0)
        n_err=failure_counts.get("errors",0)
        n_skip=(int(skips.group(1)) if skips else
                failure_counts.get("skipped",0) if failed_line else
                0 if passed else None)
        details["tests"]={
            "status":"PASS" if passed else "FAIL",
            "executed":executed,
            "skipped":n_skip,
            "failed":0 if passed else n_fail+n_err if failed_line else "SEE_TEST_LOG",
            "failures":n_fail if failed_line or passed else None,
            "errors":n_err if failed_line or passed else None,
            "exit_code":process.returncode,"log":"tests.log",
        }
        if not passed:
            # CI used to report only SEE_TEST_LOG, hiding the failing test
            # inside an ephemeral temp directory. Print bounded unittest
            # failure sections without dumping successful test output.
            markers=list(re.finditer(r"(?m)^(?:FAIL|ERROR): [^\n]+$", text))
            if markers:
                print("All failing test names (up to 80):",file=sys.stderr)
                for item in markers[:80]:
                    print("  "+item.group(0)[:280],file=sys.stderr)
            for item in markers[:5]:
                section=text[item.start():]
                stop=section.find("\n======================================================================",1)
                if stop>=0:
                    section=section[:stop]
                print("Unittest failure diagnostic:\n"+section[:2400],file=sys.stderr)
            tail=re.search(r"(?m)^FAILED \([^\n]+\)$",text)
            if tail:
                print(tail.group(0),file=sys.stderr)
            if not markers:
                print("Unittest exit code:",process.returncode,
                      "last lines:", "\n".join(text.splitlines()[-12:])[:1600],
                      file=sys.stderr)
    except subprocess.TimeoutExpired:
        details["tests"]["status"]="FAIL"
        details["tests"]["reason_code"]="TEST_TIMEOUT"
        details["tests"]["log"]="tests.log"
    except (OSError,UnicodeError,RuntimeError,SyntaxError) as exc:
        details["syntax"]["status"]="FAIL"
        details["tests"]["status"]="FAIL"
        details["error_type"]=type(exc).__name__
    details["utc_finished"]=datetime.now(timezone.utc).isoformat()
    details["result"]="PASS" if (
        details["syntax"]["status"]=="PASS"
        and details["tests"]["status"]=="PASS"
    ) else "FAIL"
    summary=output/"summary.json"
    with summary.open("x",encoding="utf-8") as file:
        json.dump(details,file,ensure_ascii=False,indent=2)
    print(json.dumps({"result":details["result"],"mode":details["mode"],
                       "source_sha":sha,"source_sha_check":sha_state,
                       "syntax":details["syntax"],"tests":details["tests"],
                       "summary_path":str(summary)},ensure_ascii=False,indent=2))
    return 0 if details["result"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
