"""
Module: src/operational_run_ledger.py
Objective: Phase 10.24 Dedicated Operational Run Ledger & Telemetry Logger.

Enforces:
  1. Complete physical separation from decision, outcome, evaluation, and governance ledgers.
  2. Append-only, hash-chained persistence with SHA-256 payload integrity reference.
  3. Safe cross-process synchronization using kernel file locking.
  4. Interrupted/truncated write detection via pre-write scan.
  5. Strict redaction: No sensitive environment variables, secrets, or full response bodies stored.
  6. Preserves operational telemetry: unique run_id, action, timestamps, durations,
     git revision, counts of attempts, successes, failures, artifacts, verified/unverified/rejected
     notices, transitions, and sanitized error summaries.
"""

import os
import sys
import json
import time
import hashlib
import datetime
from typing import Dict, List, Optional, Any

# Cross-platform kernel file locking
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

DEFAULT_OPERATIONAL_RUN_LEDGER_PATH = os.path.join("data", "processed", "operational_run_ledger.jsonl")
CURRENT_GIT_REVISION = "4ad5e13"


def get_git_revision() -> str:
    """Returns the current git HEAD commit SHA, falling back gracefully."""
    try:
        import subprocess
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        if out:
            return out
    except Exception:
        pass
    return CURRENT_GIT_REVISION


class OperationalRunLogger:
    """
    Manages append-only recording and validation of operational task runner runs.
    """
    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path or DEFAULT_OPERATIONAL_RUN_LEDGER_PATH
        self.lock_file_path = self.ledger_path + ".lock"
        os.makedirs(os.path.dirname(os.path.abspath(self.ledger_path)), exist_ok=True)

    def _acquire_process_lock(self, timeout_sec: float = 10.0) -> int:
        """Acquires an inter-process file lock via msvcrt (Windows) or fcntl (POSIX)."""
        lock_fd = os.open(self.lock_file_path, os.O_CREAT | os.O_RDWR)
        start_t = time.time()
        while True:
            try:
                if HAS_MSVCRT:
                    msvcrt.locking(lock_fd, msvcrt.LK_NBLCK, 1)
                elif HAS_FCNTL:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_fd
            except (IOError, OSError):
                if time.time() - start_t > timeout_sec:
                    os.close(lock_fd)
                    raise TimeoutError(f"Could not acquire operational ledger lock on {self.lock_file_path} within {timeout_sec}s")
                time.sleep(0.02)

    def _release_process_lock(self, lock_fd: int):
        """Releases the inter-process file lock."""
        try:
            if HAS_MSVCRT:
                try:
                    msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            elif HAS_FCNTL:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                except Exception:
                    pass
        finally:
            try:
                os.close(lock_fd)
            except Exception:
                pass

    def inspect_corruption(self) -> Dict[str, Any]:
        """
        Inspects the operational ledger for truncated lines or invalid JSON.
        Returns corruption status and clean lines count.
        """
        if not os.path.exists(self.ledger_path):
            return {"has_corruption": False, "record_count": 0, "error": None}

        valid_count = 0
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    json.loads(clean)
                    valid_count += 1
                except Exception as e:
                    return {
                        "has_corruption": True,
                        "corrupt_line_number": idx,
                        "corrupt_content": clean[:100],
                        "error": str(e),
                        "record_count": valid_count
                    }
        return {"has_corruption": False, "record_count": valid_count, "error": None}

    def verify_ledger_chain(self) -> Dict[str, Any]:
        """
        Verifies the cryptographic SHA-256 hash-chain of all records in the ledger.
        """
        if not os.path.exists(self.ledger_path):
            return {"valid": True, "count": 0, "message": "LEDGER_NOT_FOUND"}

        prev_hash = "GENESIS"
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    rec = json.loads(clean)
                except Exception as e:
                    return {"valid": False, "error_line": idx, "reason": f"INVALID_JSON: {e}"}

                if rec.get("previous_record_hash") != prev_hash:
                    return {
                        "valid": False,
                        "error_line": idx,
                        "run_id": rec.get("run_id"),
                        "expected_prev": prev_hash,
                        "actual_prev": rec.get("previous_record_hash")
                    }
                # Check record hash
                declared_hash = rec.get("record_hash")
                rec_copy = dict(rec)
                rec_copy.pop("record_hash", None)
                payload_str = json.dumps(rec_copy, sort_keys=True)
                calc_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
                if declared_hash != calc_hash:
                    return {
                        "valid": False,
                        "error_line": idx,
                        "run_id": rec.get("run_id"),
                        "reason": f"HASH_TAMPERED: declared {declared_hash} != calculated {calc_hash}"
                    }
                prev_hash = declared_hash

        return {"valid": True, "count": idx if 'idx' in locals() else 0, "last_hash": prev_hash}

    def log_run(self,
                action: str,
                start_time_ist: str,
                end_time_ist: str,
                duration_sec: float,
                overall_result: str,
                exit_code: int,
                source_identifier: str = "OFFICIAL_EXCHANGES",
                retrieval_attempts: int = 0,
                successful_retrievals: int = 0,
                failed_retrievals: int = 0,
                raw_artifacts_acquired: int = 0,
                artifacts_accepted_validation: int = 0,
                verified_primary_notices: int = 0,
                unverified_notices: int = 0,
                rejected_notices: int = 0,
                cutoff_conflicts: int = 0,
                candidate_transitions: int = 0,
                sanitized_errors: Optional[List[str]] = None,
                config_fingerprint: Optional[str] = None) -> Dict[str, Any]:
        """
        Appends an operational run telemetry record safely under kernel file lock.
        Fails closed with IOError if ledger corruption is detected.
        """
        lock_fd = self._acquire_process_lock()
        try:
            # Step 1: Pre-write corruption inspection
            corr = self.inspect_corruption()
            if corr["has_corruption"]:
                raise IOError(f"OPERATIONAL_LEDGER_CORRUPTION_BLOCKED: Corrupt line {corr['corrupt_line_number']} in {self.ledger_path}")

            # Step 2: Determine previous record hash
            prev_hash = "GENESIS"
            if os.path.exists(self.ledger_path) and os.path.getsize(self.ledger_path) > 0:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                    if lines:
                        last_rec = json.loads(lines[-1])
                        prev_hash = last_rec.get("record_hash", "GENESIS")

            # Step 3: Build run record
            ts_compact = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            entropy = hashlib.sha256(f"{action}_{start_time_ist}_{time.time()}".encode()).hexdigest()[:8]
            run_id = f"RUN_{ts_compact}_{entropy}"

            rec = {
                "record_type": "OPERATIONAL_RUN_TELEMETRY",
                "run_id": run_id,
                "action": action,
                "start_time_ist": start_time_ist,
                "end_time_ist": end_time_ist,
                "duration_seconds": round(duration_sec, 4),
                "git_revision": get_git_revision(),
                "config_fingerprint": config_fingerprint or "DEFAULT_CONFIG_V10_24",
                "source_identifier": source_identifier,
                "telemetry": {
                    "retrieval_attempts": retrieval_attempts,
                    "successful_retrievals": successful_retrievals,
                    "failed_retrievals": failed_retrievals,
                    "raw_artifacts_acquired": raw_artifacts_acquired,
                    "artifacts_accepted_validation": artifacts_accepted_validation,
                    "verified_primary_notices": verified_primary_notices,
                    "unverified_notices": unverified_notices,
                    "rejected_notices": rejected_notices,
                    "cutoff_conflicts": cutoff_conflicts,
                    "candidate_transitions": candidate_transitions
                },
                "overall_result": overall_result,
                "exit_code": exit_code,
                "sanitized_errors": [str(e)[:250] for e in (sanitized_errors or [])],
                "previous_record_hash": prev_hash
            }

            # Step 4: Compute record hash
            payload_str = json.dumps(rec, sort_keys=True)
            rec["record_hash"] = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            # Step 5: Append with flush and fsync
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
                f.flush()
                os.fsync(f.fileno())

            return rec
        finally:
            self._release_process_lock(lock_fd)

    def get_latest_runs(self, limit: int = 10, action: Optional[str] = None) -> List[Dict[str, Any]]:
        """Reads recent operational runs for monitoring reporting."""
        if not os.path.exists(self.ledger_path):
            return []
        runs = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                c = line.strip()
                if not c:
                    continue
                try:
                    r = json.loads(c)
                    if action is None or r.get("action") == action:
                        runs.append(r)
                except Exception:
                    pass
        return runs[-limit:]
