import dataclasses
import io
import json

import pytest
import sagemaker_job
from scoring import (
    DETECTORS,
    GPU_DETECTORS,
    ChunkScore,
    Text,
    prepare_text,
    read_jsonl,
    score_record,
    scores_file,
    text_sha256,
    write_manifest,
)

CONFIG = sagemaker_job.Config(
    profile="test",
    region="us-west-2",
    role_arn="arn:aws:iam::000000000000:role/test",
    s3_prefix="s3://bucket/jobs/",
    image_uri="image",
    instance_type="ml.g6e.xlarge",
    volume_gb=1,
    max_runtime_s=1,
)
JOB = "writing-eval-falcon-test"


@dataclasses.dataclass
class FakeS3:
    """Serves canned objects by s3 uri, as boto3's get_object does."""

    objects: dict[str, bytes]

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[f"s3://{Bucket}/{Key}"])}


@dataclasses.dataclass
class FakeSession:
    s3: FakeS3

    def client(self, service: str, config: object) -> FakeS3:
        assert service == "s3"
        return self.s3


def jsonl(rows) -> bytes:
    return "".join(json.dumps(row) + "\n" for row in rows).encode()


class TestFetch:
    def test_writes_every_detectors_valid_scores_before_raising_on_a_missing_text(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(sagemaker_job, "REPO_ROOT", tmp_path)
        texts = [
            Text(f"pairwise/merged/{task}", "pairwise", "merged", task, "r", 5, f"{task}.md")
            for task in ("a", "b", "c")
        ]
        for text in texts:
            (tmp_path / text.path).write_text(f"The **{text.topic}** passage, in words.")
        manifest = tmp_path / "manifest.jsonl"
        write_manifest(manifest, texts)
        objects = {
            sagemaker_job.job_uri(CONFIG, JOB, f"output/{name}.jsonl"): jsonl(
                score_record(
                    text.id,
                    text_sha256(prepare_text((tmp_path / text.path).read_text())),
                    DETECTORS[name],
                    [ChunkScore(5, 1.0)],
                )
                for text in texts[:2]
            )
            for name in GPU_DETECTORS
        }
        objects[sagemaker_job.job_uri(CONFIG, JOB, "output/job.json")] = b'{"texts": 2}'
        scores_dir = tmp_path / "scores"
        with pytest.raises(RuntimeError):
            sagemaker_job.fetch(CONFIG, FakeSession(FakeS3(objects)), JOB, manifest, scores_dir)
        for name in GPU_DETECTORS:
            rows = read_jsonl(scores_file(scores_dir, name))
            assert [row["id"] for row in rows] == [text.id for text in texts[:2]]
