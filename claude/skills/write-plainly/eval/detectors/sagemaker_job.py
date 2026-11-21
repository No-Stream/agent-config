#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["boto3>=1.40"]
# ///
"""Score manifest texts with Binoculars and Fast-DetectGPT in a SageMaker Processing job.

`run` uploads the texts not yet scored and the job code to S3, starts the job, waits for it and
merges its scores into the local score files. `fetch --job <name>` merges a finished job's scores,
for when `run` was interrupted. The account, role, bucket, image and instance come from a TOML
config (keys in README.md), which stays out of the repo.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from scoring import (
    DETECTORS,
    GPU_DETECTORS,
    MANIFEST_FILE,
    PRIVATE_DETECTORS,
    REPO_ROOT,
    SCORES_DIR,
    prepared_texts,
    read_manifest,
    require_scored,
    reusable_scores,
    scores_file,
    split_pending,
    text_sha256,
    write_scores,
)

logger: logging.Logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
JOB_PREFIX = "writing-eval-falcon"
CODE_FILES = ("scoring.py", "job_entry.py")
CONTAINER_INPUT = "/opt/ml/processing/input"
CONTAINER_OUTPUT = "/opt/ml/processing/output"
TEXTS_FILE = "texts.jsonl"
POLL_SECONDS = 60
TERMINAL = {"Completed", "Failed", "Stopped"}
RETRIES = BotoConfig(retries={"max_attempts": 12, "mode": "adaptive"})  # the account is shared


@dataclass(frozen=True)
class Config:
    profile: str
    region: str
    role_arn: str
    s3_prefix: str
    image_uri: str
    instance_type: str
    volume_gb: int
    max_runtime_s: int


def load_config(path: Path) -> Config:
    return Config(**tomllib.loads(path.read_text()))


def split_s3(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"not an s3 uri: {uri}")
    bucket, _, key = uri.removeprefix("s3://").partition("/")
    return bucket, key


def job_uri(config: Config, job: str, part: str) -> str:
    return f"{config.s3_prefix.rstrip('/')}/{job}/{part}"


def put(s3, uri: str, body: bytes) -> None:
    bucket, key = split_s3(uri)
    s3.put_object(Bucket=bucket, Key=key, Body=body)


def get(s3, uri: str) -> bytes:
    bucket, key = split_s3(uri)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def pending_texts(manifest: Path, scores_dir: Path) -> dict[str, str]:
    """The prepared texts that at least one GPU detector has not scored."""
    prepared = prepared_texts(read_manifest(manifest), REPO_ROOT)
    pending: dict[str, str] = {}
    for name in GPU_DETECTORS:
        _, missing = split_pending(prepared, scores_file(scores_dir, name), DETECTORS[name])
        pending.update(missing)
    return pending


def launch(config: Config, session: boto3.Session, pending: dict[str, str]) -> str:
    job = f"{JOB_PREFIX}-{datetime.datetime.now(datetime.UTC):%Y%m%dt%H%M%S}"
    s3 = session.client("s3", config=RETRIES)
    for name in CODE_FILES:
        put(s3, job_uri(config, job, f"code/{name}"), (HERE / name).read_bytes())
    rows = [
        {"id": text_id, "sha256": text_sha256(text), "text": text}
        for text_id, text in pending.items()
    ]
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    put(s3, job_uri(config, job, f"texts/{TEXTS_FILE}"), body.encode())
    session.client("sagemaker", config=RETRIES).create_processing_job(
        ProcessingJobName=job,
        RoleArn=config.role_arn,
        AppSpecification={
            "ImageUri": config.image_uri,
            "ContainerEntrypoint": [
                "python3",
                f"{CONTAINER_INPUT}/code/job_entry.py",
                "--texts",
                f"{CONTAINER_INPUT}/texts/{TEXTS_FILE}",
                "--out",
                CONTAINER_OUTPUT,
            ],
        },
        ProcessingInputs=[
            {
                "InputName": part,
                "S3Input": {
                    "S3Uri": job_uri(config, job, f"{part}/"),
                    "LocalPath": f"{CONTAINER_INPUT}/{part}",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                },
            }
            for part in ("code", "texts")
        ],
        ProcessingOutputConfig={
            "Outputs": [
                {
                    "OutputName": "scores",
                    "S3Output": {
                        "S3Uri": job_uri(config, job, "output/"),
                        "LocalPath": CONTAINER_OUTPUT,
                        "S3UploadMode": "EndOfJob",
                    },
                }
            ]
        },
        ProcessingResources={
            "ClusterConfig": {
                "InstanceCount": 1,
                "InstanceType": config.instance_type,
                "VolumeSizeInGB": config.volume_gb,
            }
        },
        StoppingCondition={"MaxRuntimeInSeconds": config.max_runtime_s},
        Environment={"HF_HOME": "/opt/ml/processing/hf", "TOKENIZERS_PARALLELISM": "false"},
        Tags=[{"Key": "project", "Value": "agent-config-writing-eval"}],
    )
    logger.info(f"started {job} on {config.instance_type} with {len(rows)} texts")
    return job


def wait(session: boto3.Session, job: str) -> None:
    sagemaker = session.client("sagemaker", config=RETRIES)
    last = None
    while True:
        described = sagemaker.describe_processing_job(ProcessingJobName=job)
        status = described["ProcessingJobStatus"]
        state = (status, "ProcessingStartTime" in described)
        if state != last:
            logger.info(f"{job}: {status}, container started: {state[1]}")
            last = state
        if status in TERMINAL:
            if status != "Completed":
                raise RuntimeError(f"{job} {status}: {described.get('FailureReason')}")
            return
        time.sleep(POLL_SECONDS)


def fetch(
    config: Config, session: boto3.Session, job: str, manifest: Path, scores_dir: Path
) -> None:
    s3 = session.client("s3", config=RETRIES)
    prepared = prepared_texts(read_manifest(manifest), REPO_ROOT)
    wanted = {text_id: text_sha256(text) for text_id, text in prepared.items()}
    unscored = {}
    for name in GPU_DETECTORS:
        scores_path = scores_file(scores_dir, name)
        kept, _ = split_pending(prepared, scores_path, DETECTORS[name])
        lines = get(s3, job_uri(config, job, f"output/{name}.jsonl")).decode().splitlines()
        fetched = [json.loads(line) for line in lines if line.strip()]
        current = reusable_scores(fetched, wanted, DETECTORS[name])
        unscored[name] = write_scores(scores_path, prepared, {**kept, **current})
        logger.info(f"{name}: merged {len(current)} scores from {job} into {scores_path}")
    logger.info(f"{job}: {get(s3, job_uri(config, job, 'output/job.json')).decode()}")
    require_scored(unscored, job)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("run", "fetch"))
    parser.add_argument("--job", help="the job to fetch")
    parser.add_argument("--config", type=Path, default=PRIVATE_DETECTORS / "sagemaker.toml")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)
    parser.add_argument("--scores", type=Path, default=SCORES_DIR)
    args = parser.parse_args()
    config = load_config(args.config)
    session = boto3.Session(profile_name=config.profile, region_name=config.region)
    if args.command == "fetch":
        if not args.job:
            parser.error("fetch needs --job")
        fetch(config, session, args.job, args.manifest, args.scores)
        return
    pending = pending_texts(args.manifest, args.scores)
    if not pending:
        logger.info("every text already has Binoculars and Fast-DetectGPT scores")
        return
    job = launch(config, session, pending)
    wait(session, job)
    fetch(config, session, job, args.manifest, args.scores)


if __name__ == "__main__":
    main()
